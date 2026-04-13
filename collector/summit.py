"""Summit One Vanderbilt scraper (Gateway Ticketing).

Approach:
- Load ticketing page, dismiss cookie banner, open calendar
- Trigger price data load by clicking one tour time
- Read full priceSchedule (time-range → price per program) from Angular scope
- Walk through months: read all available days with priceProgramId (from day.ariaLabel + scope)
- For each available day, click it → read eventTimes (time + availability) from Angular scope
- Compute price per tour time using priceSchedule lookup (no per-tour-time clicking needed)
"""

import asyncio
import re
from datetime import date, datetime
from .base import BaseScraper

SUMMIT_TICKETING_URL = "https://tickets.summitov.com/Webstore/shop/viewitems.aspx?CG=sum&C=adm"


def _time_str_to_mins(t: str) -> int:
    """Convert 'HH:MM' string (24h) to minutes since midnight. Empty string → 0."""
    if not t:
        return 0
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _slot_to_mins(tour_time: str) -> int:
    """Convert '10:30 AM' tour time label to minutes since midnight."""
    m = re.match(r"(\d+):(\d+)\s*(AM|PM)", tour_time, re.I)
    if not m:
        return 0
    h, mn, ap = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if ap == "PM" and h != 12:
        h += 12
    if ap == "AM" and h == 12:
        h = 0
    return h * 60 + mn


def _lookup_price(price_schedule: list[dict], program_id: int, slot_mins: int) -> int | None:
    """Return price in dollars for a given program + tour time (minutes since midnight)."""
    for entry in price_schedule:
        if entry["PriceProgramId"] != program_id:
            continue
        start = _time_str_to_mins(entry["EffectiveStartTime"])
        end = _time_str_to_mins(entry["EffectiveEndTime"])
        # Start of "" means midnight (0), end means 23:59 (1439)
        if end == 0:
            end = 1439
        if start <= slot_mins <= end:
            return entry["Price"]
    return None


def _parse_aria_date(aria_label: str) -> str | None:
    """Parse 'M/D/YYYY' from aria-label to 'YYYY-MM-DD'. Returns None for past/other dates."""
    if not aria_label:
        return None
    m = re.match(r"(\d+)/(\d+)/(\d{4})", aria_label.strip())
    if not m:
        return None
    month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{year:04d}-{month:02d}-{day:02d}"


def _month_prefix(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}-"


class SummitScraper(BaseScraper):
    """Scrape Summit One Vanderbilt pricing via Angular DOM + priceSchedule."""

    async def _wait_for_calendar_scope(self, page, timeout_ms: int = 15000) -> bool:
        """Wait until Angular calendar state is present before reading it."""
        for _ in range(timeout_ms // 500):
            ready = await page.evaluate("""() => {
                try {
                    const table = document.querySelector('table.calendar');
                    if (!table || typeof angular === 'undefined') return false;
                    const scope = angular.element(table).scope();
                    return !!(
                        scope &&
                        scope.viewModel &&
                        scope.viewModel.calendar &&
                        Array.isArray(scope.viewModel.calendar.days)
                    );
                } catch(e) {
                    return false;
                }
            }""")
            if ready:
                return True
            await page.wait_for_timeout(500)
        return False

    async def _dismiss_cookie_banner(self, page):
        try:
            await page.evaluate("""() => {
                const sdk = document.getElementById('onetrust-consent-sdk');
                if (sdk) sdk.remove();
                const btn = document.getElementById('onetrust-accept-btn-handler');
                if (btn) btn.click();
            }""")
            await page.wait_for_timeout(800)
        except Exception:
            pass

    async def _dismiss_overlay(self, page):
        """Remove OneTrust overlay — call before any click that might be blocked."""
        await page.evaluate("""() => {
            const sdk = document.getElementById('onetrust-consent-sdk');
            if (sdk) sdk.remove();
        }""")

    async def _ensure_ticketing_page(self, page):
        """Ensure we're on the Gateway ticketing page that has Angular calendar controls."""
        has_calendar_button = await page.evaluate(
            "() => !!document.querySelector('.shared-calendar-button')"
        )
        if has_calendar_button:
            return

        # If started from summitov.com marketing page, follow Buy Now ticket link.
        link = await page.evaluate("""() => {
            const links = [...document.querySelectorAll('a[href]')];
            const pick = links.find(a => {
                const href = (a.getAttribute('href') || '').toLowerCase();
                return href.includes('tickets.summitov.com')
                    && href.includes('viewitems')
                    && href.includes('c=adm');
            });
            return pick ? pick.href : null;
        }""")
        target = link or SUMMIT_TICKETING_URL
        print(f"  [Summit] Navigating to ticketing page: {target}")
        await page.goto(target, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)
        await self._dismiss_cookie_banner(page)

        has_calendar_button = await page.evaluate(
            "() => !!document.querySelector('.shared-calendar-button')"
        )
        if not has_calendar_button:
            raise RuntimeError(
                "Summit ticketing controls not found after navigating to ticketing page"
            )

    async def _load_price_schedule(self, page) -> list[dict]:
        """Open calendar, select a day, click one tour time to trigger priceSchedule load."""
        # Remove OneTrust overlay then click calendar button via JS to avoid pointer interception
        await self._dismiss_overlay(page)
        clicked = await page.evaluate("""() => {
            const btn = document.querySelector('.shared-calendar-button')
                || [...document.querySelectorAll('button,a')].find(el => {
                    const t = (el.innerText || el.textContent || '').trim();
                    return /select\\s*date\\s*\\/?\\s*time/i.test(t);
                });
            if (!btn) return false;
            btn.click();
            return true;
        }""")
        if not clicked:
            raise RuntimeError("Could not find Select Date/Time button")
        await page.wait_for_timeout(2000)

        if not await self._wait_for_calendar_scope(page):
            raise RuntimeError("Summit calendar scope did not load")

        # Select first available day
        selected = await page.evaluate("""() => {
            const scope = angular.element(document.querySelector('table.calendar')).scope();
            const avail = scope.viewModel.calendar.days.find(d => d.available && !d.other);
            if (!avail) return null;
            scope.selectDay(avail);
            scope.$apply();
            return avail.ariaLabel;
        }""")
        if not selected:
            raise RuntimeError("No available days found in calendar")
        await page.wait_for_timeout(2000)

        # Click first available tour time via JS to avoid overlay interference
        await self._dismiss_overlay(page)
        clicked_time = await page.evaluate("""() => {
            const btn = document.querySelector('button.select-time:not(.disabled)');
            if (!btn) return false;
            btn.click();
            return true;
        }""")
        if not clicked_time:
            raise RuntimeError("No available tour time button found")
        await page.wait_for_timeout(1500)

        # Extract priceSchedule
        schedule = await page.evaluate("""() => {
            const el = document.querySelector('[ng-repeat*="item in subCategory.items"]');
            if (!el) return [];
            const scope = angular.element(el).scope();
            const ps = scope.item.priceSchedule;
            const result = [];
            for (const k in ps) {
                const e = ps[k];
                if (typeof e === 'object' && e !== null && e.Price !== undefined) {
                    result.push({
                        PriceProgramId: e.PriceProgramId,
                        EffectiveStartTime: e.EffectiveStartTime || '',
                        EffectiveEndTime: e.EffectiveEndTime || '23:59',
                        Price: e.Price,
                    });
                }
            }
            return result;
        }""")
        return schedule

    async def _get_month_days(self, page) -> list[dict]:
        """Read all visible calendar day objects from Angular scope."""
        return await page.evaluate("""() => {
            try {
                const scope = angular.element(document.querySelector('table.calendar')).scope();
                const days = scope.viewModel.calendar.days || [];
                return days.map(d => ({
                    ariaLabel: d.ariaLabel || '',
                    available: !!d.available,
                    selected: !!d.selected,
                    other: !!d.other,
                    priceProgramId: d.priceProgramId,
                }));
            } catch(e) {
                return [];
            }
        }""")

    async def _get_visible_month_year(self, page) -> tuple[int, int] | None:
        """Return the currently visible calendar year/month from Angular scope."""
        result = await page.evaluate("""() => {
            try {
                const scope = angular.element(document.querySelector('table.calendar')).scope();
                return {
                    month: parseInt(scope.viewModel.calendar.month, 10),
                    year: parseInt(scope.viewModel.calendar.year, 10),
                };
            } catch(e) {
                return null;
            }
        }""")
        if not result:
            return None
        return result["year"], result["month"]

    async def _wait_for_month_ready(self, page, month: int, year: int, timeout_ms: int = 15000) -> bool:
        """Wait until the calendar grid reflects the requested month."""
        target_prefix = _month_prefix(year, month)
        for _ in range(max(1, timeout_ms // 500)):
            visible = await self._get_visible_month_year(page)
            days = await self._get_month_days(page)
            current_month_days = []
            for day in days:
                if day.get("other"):
                    continue
                parsed = _parse_aria_date(day.get("ariaLabel", ""))
                if parsed:
                    current_month_days.append(parsed)

            if (
                visible == (year, month)
                and current_month_days
                and all(day.startswith(target_prefix) for day in current_month_days)
            ):
                return True

            await page.wait_for_timeout(500)
        return False

    async def _navigate_to_month(self, page, month: int, year: int) -> bool:
        """Navigate the calendar to the given month/year using the site's Angular arrows."""
        try:
            visible = await self._get_visible_month_year(page)
            if not visible:
                return False

            current_year, current_month = visible
            current_index = current_year * 12 + current_month
            target_index = year * 12 + month
            if current_index == target_index:
                return await self._wait_for_month_ready(page, month, year)

            step_selector = (
                "span[ng-click='nextMonth()']"
                if target_index > current_index
                else "span[ng-click='prevMonth()']"
            )
            steps = abs(target_index - current_index)

            for _ in range(steps):
                before = await self._get_visible_month_year(page)
                if not before:
                    return False
                await page.evaluate(
                    """(selector) => {
                        const btn = document.querySelector(selector);
                        if (btn) btn.click();
                    }""",
                    step_selector,
                )
                await page.wait_for_function(
                    """([prevYear, prevMonth]) => {
                        try {
                            const scope = angular.element(document.querySelector('table.calendar')).scope();
                            return parseInt(scope.viewModel.calendar.year, 10) !== prevYear
                                || parseInt(scope.viewModel.calendar.month, 10) !== prevMonth;
                        } catch(e) {
                            return false;
                        }
                    }""",
                    arg=[before[0], before[1]],
                    timeout=10000,
                )
                await page.wait_for_timeout(1200)

            visible = await self._get_visible_month_year(page)
            if visible != (year, month):
                return False
            return await self._wait_for_month_ready(page, month, year)
        except Exception:
            return False

    async def _read_selected_times(self, page) -> dict:
        """Read the selected day and any rendered event times."""
        return await page.evaluate("""() => {
            try {
                const scope = angular.element(document.querySelector('table.calendar')).scope();
                const days = scope.viewModel.calendar.days || [];
                const selected = days.find(d => d.selected);
                const times = scope.viewModel.calendar.eventTimes || [];
                return {
                    selectedAria: selected ? (selected.ariaLabel || '') : '',
                    times: times.map(e => ({
                        time: e.time || '',
                        availability: (e.availability || '').toLowerCase(),
                        disabled: !!e.disabled,
                    })),
                };
            } catch(e) {
                return { selectedAria: '', times: [] };
            }
        }""")

    async def _get_times_for_day(self, page, day_scope_obj: dict) -> list[dict]:
        """Click a calendar day and read its tour time names + availability."""
        aria = day_scope_obj.get("ariaLabel", "")
        for attempt in range(3):
            selected = await page.evaluate("""(aria) => {
                try {
                    const scope = angular.element(document.querySelector('table.calendar')).scope();
                    const day = scope.viewModel.calendar.days.find(d => d.ariaLabel === aria);
                    if (!day) return false;
                    scope.selectDay(day);
                    scope.$apply();
                    return true;
                } catch(e) {
                    return false;
                }
            }""", aria)

            if not selected:
                return []

            for _ in range(12):
                payload = await self._read_selected_times(page)
                if payload.get("selectedAria") == aria and payload.get("times"):
                    return payload["times"]
                await page.wait_for_timeout(500)

            print(f"  [Summit] {aria}: eventTimes still empty after attempt {attempt + 1}, retrying")
            await page.wait_for_timeout(1000 * (attempt + 1))

        return []

    async def run(self, start_date: str, end_date: str) -> list[dict]:
        """Scrape Summit prices for the given date range."""
        await self.start_browser()
        results = []

        try:
            page = await self.new_page()
            print(f"  [Summit] Loading page...")
            await page.goto(self.venue_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            await self._dismiss_cookie_banner(page)
            await self._ensure_ticketing_page(page)

            print(f"  [Summit] Loading price schedule...")
            price_schedule = await self._load_price_schedule(page)
            if not price_schedule:
                print("  [Summit] ERROR: Empty price schedule")
                return []
            print(f"  [Summit] Loaded {len(price_schedule)} price schedule entries")

            # Close the "select time" step and reopen calendar cleanly via Angular
            await page.evaluate("""() => {
                try {
                    // Try calling Angular closePageCalendar
                    const btn = document.querySelector('button[ng-click*="closePageCalendar"]');
                    if (btn) {
                        const scope = angular.element(btn).scope();
                        const item = scope.item || scope.subCategory?.items?.[0];
                        const shared = scope.shared;
                        if (scope.closePageCalendar) scope.closePageCalendar(item);
                        scope.$apply();
                    }
                } catch(e) {}
            }""")
            await page.wait_for_timeout(800)
            # Reopen calendar via JS to avoid any overlay interference
            await self._dismiss_overlay(page)
            await page.evaluate("""() => {
                const btn = document.querySelector('.shared-calendar-button');
                if (btn) btn.click();
            }""")
            await page.wait_for_timeout(2000)

            start_dt = date.fromisoformat(start_date)
            end_dt = date.fromisoformat(end_date)
            processed_dates = set()

            # Build list of (year, month) tuples to visit
            months_to_visit = set()
            cur = date(start_dt.year, start_dt.month, 1)
            end_first = date(end_dt.year, end_dt.month, 1)
            while cur <= end_first:
                months_to_visit.add((cur.year, cur.month))
                if cur.month == 12:
                    cur = date(cur.year + 1, 1, 1)
                else:
                    cur = date(cur.year, cur.month + 1, 1)

            for (yr, mo) in sorted(months_to_visit):
                print(f"  [Summit] Navigating to {yr}-{mo:02d}...")
                ok = await self._navigate_to_month(page, mo, yr)
                if not ok:
                    print(f"  [Summit] Could not navigate to {yr}-{mo:02d}")
                    continue

                target_prefix = _month_prefix(yr, mo)
                days = [
                    day for day in await self._get_month_days(page)
                    if not day["other"]
                    and (_parse_aria_date(day.get("ariaLabel", "")) or "").startswith(target_prefix)
                ]
                if not days:
                    print(f"  [Summit] {yr}-{mo:02d}: no target-month days rendered")
                    continue

                month_processed_before = len(processed_dates)

                for day_obj in days:
                    # Include days with a priceProgramId even if available=False
                    # (they have pricing but may be sold out or not yet open)
                    if not day_obj["available"] and not day_obj.get("priceProgramId"):
                        continue
                    full_date = _parse_aria_date(day_obj["ariaLabel"])
                    if not full_date:
                        continue
                    if full_date < start_date or full_date > end_date:
                        continue
                    if full_date in processed_dates:
                        continue

                    program_id = day_obj.get("priceProgramId")
                    if not program_id:
                        continue

                    # Get tour times for this day
                    times = await self._get_times_for_day(page, day_obj)
                    if not times:
                        print(f"  [Summit] {full_date}: no eventTimes after retries; skipping")
                        continue

                    for t in times:
                        time_label = t["time"]
                        avail = t["availability"]
                        if avail == "sold out" or t["disabled"]:
                            status = "sold_out"
                        elif "fast" in avail or "limited" in avail:
                            status = "going_fast"
                        else:
                            status = "available"

                        slot_mins = _slot_to_mins(time_label)
                        price = _lookup_price(price_schedule, program_id, slot_mins)

                        results.append({
                            "travel_date": full_date,
                            "tour_time": time_label,
                            "price_cents": price * 100 if price is not None else None,
                            "currency": "USD",
                            "status": status,
                        })

                    processed_dates.add(full_date)
                    print(f"  [Summit] {full_date}: {len(times)} tour times, program={program_id}")
                    await self.delay(0.3)

                month_processed = len(processed_dates) - month_processed_before
                print(f"  [Summit] {yr}-{mo:02d}: captured {month_processed} dates")

            print(f"  [Summit] Done: {len(results)} price entries for {len(processed_dates)} dates")
            await page.close()

        except Exception as e:
            print(f"  [Summit] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.close()

        return results