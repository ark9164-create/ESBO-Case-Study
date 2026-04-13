"""Shared Ventrata modal scraper base class.

Both Edge and Top of the Rock use the Ventrata checkout modal triggered by
a button click. Once open the modal has identical [data-cy] DOM structure.
"""

import asyncio
import re
from datetime import date
from .base import BaseScraper


_JS_FIND_IN_SHADOW = """
function findInShadow(root, selector) {
    let results = [...root.querySelectorAll(selector)];
    root.querySelectorAll('*').forEach(el => {
        if (el.shadowRoot) results = results.concat(findInShadow(el.shadowRoot, selector));
    });
    return results;
}
"""

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_price_text(text: str) -> int | None:
    """Parse '$46' or '$46.00' → cents (4600)."""
    if not text:
        return None
    m = re.search(r"\$(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    return int(round(float(m.group(1)) * 100))


def _parse_month_year(text: str) -> tuple[int, int] | None:
    """Parse 'March 2026' → (2026, 3)."""
    m = re.search(r"(\w+)\s+(\d{4})", text, re.I)
    if not m:
        return None
    mo = _MONTH_MAP.get(m.group(1).lower())
    if not mo:
        return None
    return int(m.group(2)), mo


class VentrataBaseScraper(BaseScraper):
    """Base scraper for observation deck attractions using the Ventrata checkout modal.

    Subclasses must define:
      - venue_label: str  — display name for log messages
      - product_id: str   — Ventrata product UUID for General Admission

    Subclasses may override _open_modal() if the button trigger differs.
    """

    venue_label: str = "Ventrata"
    product_id: str = ""

    async def _open_modal(self, page) -> bool:
        """Click the button that triggers the Ventrata checkout modal.

        Checks ventrata-checkout-element (new Ventrata v3 widget), ventrata-checkout
        attr (Edge), and bare data-config (TOTR legacy).

        The v3 widget wraps buttons in a <ventrata-checkout-element> custom element
        that intercepts pointer events — we must click that wrapper, not the inner button.
        """
        pid = self.product_id

        # v3: <ventrata-checkout-element data-app-name="root-app::{pid}::...">
        if pid:
            els = page.locator(f'ventrata-checkout-element[data-app-name*="{pid}"]')
            if await els.count() > 0:
                try:
                    await els.first.click(timeout=5000)
                    return True
                except Exception:
                    pass

        # Any ventrata-checkout-element
        els = page.locator("ventrata-checkout-element")
        if await els.count() > 0:
            try:
                await els.first.click(timeout=5000)
                return True
            except Exception:
                pass

        return await page.evaluate(f"""() => {{
            const pid = '{pid}';
            // Edge-style: [ventrata-checkout] with data-config
            const vt = document.querySelectorAll('[ventrata-checkout]');
            for (const b of vt) {{
                const cfg = b.getAttribute('data-config') || '';
                if (!pid || cfg.includes(pid)) {{ b.click(); return true; }}
            }}
            // TOTR/generic style: button[data-config] containing productID
            const dc = document.querySelectorAll('button[data-config], a[data-config]');
            for (const b of dc) {{
                const cfg = b.getAttribute('data-config') || '';
                if (!pid || cfg.includes(pid)) {{ b.click(); return true; }}
            }}
            return false;
        }}""")

    async def _wait_for_modal(self, page, timeout_ms: int = 10000) -> bool:
        """Wait for the Ventrata modal to appear (tiers-view or calendar wrapper)."""
        for _ in range(timeout_ms // 500):
            found = await page.evaluate(f"""() => {{
                {_JS_FIND_IN_SHADOW}
                return findInShadow(document, '[data-cy="tiers-view"], [data-cy="popup-container"]').length > 0;
            }}""")
            if found:
                return True
            await page.wait_for_timeout(500)
        return False

    async def _pre_calendar_setup(self, page) -> None:
        """Optional setup after modal opens, before calendar is read.

        Override in subclasses that need extra steps (e.g. incrementing
        ticket quantity) before the calendar shows available dates.
        """
        pass

    async def _wait_for_calendar(self, page, timeout_ms: int = 20000) -> bool:
        """Wait for calendar day buttons to load inside the Ventrata shadow DOM."""
        for _ in range(timeout_ms // 500):
            found = await page.evaluate(f"""() => {{
                {_JS_FIND_IN_SHADOW}
                return findInShadow(document, '[data-cy="calendar-day"], [data-cy="calendar-day-active"]').length > 0;
            }}""")
            if found:
                return True
            await page.wait_for_timeout(500)
        return False

    async def _get_current_month(self, page) -> tuple[int, int] | None:
        text = await page.evaluate(f"""() => {{
            {_JS_FIND_IN_SHADOW}
            const el = findInShadow(document, '[data-cy="month-info"]')[0];
            return el ? el.textContent.trim() : null;
        }}""")
        return _parse_month_year(text) if text else None

    async def _navigate_to_month(self, page, year: int, month: int) -> bool:
        """Navigate the calendar to the target month/year."""
        for _ in range(24):
            current = await self._get_current_month(page)
            if not current:
                return False
            cy, cm = current
            if cy == year and cm == month:
                return True
            direction = "right" if (cy, cm) < (year, month) else "left"
            clicked = await page.evaluate(f"""() => {{
                {_JS_FIND_IN_SHADOW}
                const btn = findInShadow(document, '[data-cy="month-navigation-{direction}"]')[0];
                if (btn && !btn.disabled) {{ btn.click(); return true; }}
                return false;
            }}""")
            if not clicked:
                return False
            await page.wait_for_timeout(800)
        return False

    async def _get_available_days(self, page) -> list[int]:
        """Return list of non-disabled day numbers in the current calendar view."""
        return await page.evaluate(f"""() => {{
            {_JS_FIND_IN_SHADOW}
            const days = findInShadow(
                document,
                '[data-cy="calendar-day"], [data-cy="calendar-day-active"]'
            );
            return days
                .filter(d => !d.hasAttribute('disabled'))
                .map(d => {{
                    const n = d.querySelector('[data-cy="day-number"]');
                    return n ? parseInt(n.textContent.trim()) : null;
                }})
                .filter(n => n);
        }}""")

    async def _click_day(self, page, day_num: int) -> bool:
        """Click a specific day number in the calendar."""
        return await page.evaluate(f"""() => {{
            {_JS_FIND_IN_SHADOW}
            const days = findInShadow(
                document,
                '[data-cy="calendar-day"], [data-cy="calendar-day-active"]'
            );
            for (const d of days) {{
                const n = d.querySelector('[data-cy="day-number"]');
                if (n && parseInt(n.textContent.trim()) === {day_num} && !d.hasAttribute('disabled')) {{
                    d.click();
                    return true;
                }}
            }}
            return false;
        }}""")

    async def _get_active_day(self, page) -> int | None:
        """Return the selected calendar day number, if any."""
        return await page.evaluate(f"""() => {{
            {_JS_FIND_IN_SHADOW}
            const active = findInShadow(document, '[data-cy="calendar-day-active"]')[0];
            if (!active) return null;
            const n = active.querySelector('[data-cy="day-number"]');
            return n ? parseInt(n.textContent.trim()) : null;
        }}""")

    async def _get_tour_times(self, page) -> list[dict]:
        """Read tour times, prices, and group labels from the Ventrata tour time view.

        The Ventrata v3 widget (Edge, TOR) does not expose a textual tour-group
        label in its GA DOM — the sunset/morning/evening tier is a price-only
        signal. We only populate `tour_group` when a timeslot has an explicit,
        non-badge label element inside it (a real in-slot group tag). The
        day-floor "Best price" indicator at `[data-cy="best-offer-badge"]` is
        excluded — it is a dynamic-pricing hint, not a tour group.
        """
        return await page.evaluate(f"""() => {{
            {_JS_FIND_IN_SHADOW}
            const slots = findInShadow(document, '[data-cy="timeslot"]');

            // Only accept a real in-slot label element. Exclude the best-price
            // badge, sold-out label, time label, and price label — those are
            // not tour-group tags.
            function findInSlotLabel(slotEl) {{
                const labelEl = slotEl.querySelector(
                    '[data-cy*="group"], [data-cy*="tag"], [data-cy="tour-group-label"]'
                );
                if (labelEl) {{
                    const t = (labelEl.textContent || '').trim();
                    if (t) return t;
                }}
                return null;
            }}

            return slots.map(s => {{
                const timeEl = s.querySelector('[data-cy="time-label"]');
                const priceEl = s.querySelector('[data-cy="time-slot-price"]');
                const input = s.querySelector('input');
                const soldOut = input ? input.disabled : s.classList.contains('cursor-not-allowed');

                const timeTxt = timeEl ? timeEl.textContent.trim() : '';
                const priceTxt = priceEl ? priceEl.textContent.trim() : '';

                return {{
                    time: timeTxt,
                    price_text: priceTxt,
                    sold_out: soldOut,
                    tour_group: findInSlotLabel(s),
                }};
                }}).filter(s => s.time);
        }}""")

    async def _load_day_slots(self, page, day_num: int, attempts: int = 4) -> list[dict]:
        """Retry date selection until the widget renders tour times for a day."""
        for attempt in range(attempts):
            active_day = await self._get_active_day(page)
            if active_day != day_num:
                if not await self._click_day(page, day_num):
                    return []
                for _ in range(8):
                    if await self._get_active_day(page) == day_num:
                        break
                    await page.wait_for_timeout(250)

            for _ in range(12):
                slots = await self._get_tour_times(page)
                if slots:
                    return slots
                await page.wait_for_timeout(250)

            await page.wait_for_timeout(500 * (attempt + 1))

        return []

    async def run(self, start_date: str, end_date: str) -> list[dict]:
        """Scrape prices for the given date range via the Ventrata modal."""
        await self.start_browser()
        results = []
        label = self.venue_label

        try:
            page = await self.new_page()
            print(f"  [{label}] Loading page...")
            await page.goto(self.venue_url, wait_until="domcontentloaded", timeout=180000)
            await page.wait_for_timeout(6000)

            print(f"  [{label}] Opening modal...")
            if not await self._open_modal(page):
                print(f"  [{label}] ERROR: Could not find booking button")
                return []
            # Wait for modal to open before any setup steps
            if not await self._wait_for_modal(page):
                print(f"  [{label}] WARNING: Modal slow to open, proceeding anyway")
            await self._pre_calendar_setup(page)

            print(f"  [{label}] Waiting for calendar...")
            if not await self._wait_for_calendar(page):
                print(f"  [{label}] ERROR: Calendar did not appear")
                return []
            print(f"  [{label}] Calendar found")

            start_dt = date.fromisoformat(start_date)
            end_dt = date.fromisoformat(end_date)
            processed_dates: set[str] = set()

            months_to_visit: set[tuple[int, int]] = set()
            cur = date(start_dt.year, start_dt.month, 1)
            end_first = date(end_dt.year, end_dt.month, 1)
            while cur <= end_first:
                months_to_visit.add((cur.year, cur.month))
                next_month = cur.month % 12 + 1
                next_year = cur.year + (cur.month == 12)
                cur = date(next_year, next_month, 1)

            for (yr, mo) in sorted(months_to_visit):
                print(f"  [{label}] Navigating to {yr}-{mo:02d}...")
                if not await self._navigate_to_month(page, yr, mo):
                    print(f"  [{label}] Could not navigate to {yr}-{mo:02d}")
                    continue
                # Wait for day buttons to load (availability API may take a moment)
                await self._wait_for_calendar(page, timeout_ms=10000)

                available_days = await self._get_available_days(page)
                print(f"  [{label}] {yr}-{mo:02d}: {len(available_days)} available days")

                for day_num in available_days:
                    full_date = f"{yr:04d}-{mo:02d}-{day_num:02d}"
                    if full_date < start_date or full_date > end_date:
                        continue
                    if full_date in processed_dates:
                        continue

                    slots = await self._load_day_slots(page, day_num)
                    if not slots:
                        print(f"  [{label}] WARNING: No tour times loaded for {full_date}")
                        continue

                    for s in slots:
                        results.append({
                            "travel_date": full_date,
                            "tour_time": s["time"],
                            "price_cents": _parse_price_text(s["price_text"]),
                            "currency": "USD",
                            "status": "sold_out" if s["sold_out"] else "available",
                            "tour_group": s.get("tour_group"),
                        })

                    processed_dates.add(full_date)
                    print(f"  [{label}] {full_date}: {len(slots)} tour times")
                    await self.delay(0.3)

            print(f"  [{label}] Done: {len(results)} price entries for {len(processed_dates)} dates")
            await page.close()

        except Exception as e:
            print(f"  [{label}] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.close()

        return results
