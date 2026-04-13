"""Top of the Rock scraper (Ventrata modal widget, DOM parsing only).

TOTR uses Ventrata with timePickerType:'select' which renders a popover
time picker instead of the list-based tour times Edge uses.

Key data-cy selectors:
  - popoverTimePicker: the time picker container
  - popoverTimeslot-available: an available tour time button (site selector, do not rename)
  - popoverTimeslot-unavailable: a sold-out tour time button (site selector, do not rename)
"""

from .ventrata_base import VentrataBaseScraper, _JS_FIND_IN_SHADOW


class TotrScraper(VentrataBaseScraper):
    """Scrape Top of the Rock pricing via Ventrata checkout modal DOM."""

    venue_label = "TOTR"
    product_id = "6dceebaf-4454-4f02-a605-a7d1593b2200"  # Top of the Rock General Admission ($42-$71)

    async def _pre_calendar_setup(self, page) -> None:
        """TOTR defaults to 0 adults — increment to 1 to trigger calendar pricing."""
        await page.evaluate(f"""() => {{
            {_JS_FIND_IN_SHADOW}
            const btn = findInShadow(document, '[data-cy="increase-button"]')[0];
            if (btn) btn.click();
        }}""")
        await page.wait_for_timeout(2000)

    async def _get_tour_times(self, page) -> list[dict]:
        """Read tour times from TOTR's popover time picker."""
        # Try the standard list-based tour times first (Edge-style)
        slots = await super()._get_tour_times(page)
        if slots:
            return slots

        # TOTR: read from popoverTimeslot-available / popoverTimeslot-unavailable (site selectors)
        return await page.evaluate(f"""() => {{
            {_JS_FIND_IN_SHADOW}
            const available = findInShadow(document, '[data-cy="popoverTimeslot-available"]');
            const unavailable = findInShadow(document, '[data-cy="popoverTimeslot-unavailable"]');

            function parseSlot(el, soldOut) {{
                // Text is like "9:00 AM $47" or "5:30 PM  Sunset $59"
                const text = el.textContent.trim();
                // Extract time: first occurrence of H:MM AM/PM
                const timeMatch = text.match(/(\\d{{1,2}}:\\d{{2}}\\s*(?:AM|PM))/i);
                if (!timeMatch) return null;
                let time = timeMatch[1];
                // Check for Sunset/etc label (between AM/PM and $price)
                const labelMatch = text.match(/(?:AM|PM)\\s+([A-Za-z]+)/i);
                if (labelMatch && labelMatch[1].trim()) {{
                    time = time + ' ' + labelMatch[1].trim();
                }}
                // Extract price
                const priceMatch = text.match(/(\\$\\d+(?:\\.\\d+)?)/);
                return {{
                    time: time,
                    price_text: priceMatch ? priceMatch[1] : '',
                    sold_out: soldOut,
                }};
            }}

            const results = [];
            const seen = new Set();
            for (const el of available) {{
                const slot = parseSlot(el, false);
                if (slot && !seen.has(slot.time)) {{
                    seen.add(slot.time);
                    results.push(slot);
                }}
            }}
            for (const el of unavailable) {{
                const slot = parseSlot(el, true);
                if (slot && !seen.has(slot.time)) {{
                    seen.add(slot.time);
                    results.push(slot);
                }}
            }}
            return results;
        }}""")
