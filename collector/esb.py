"""Empire State Building scraper (checkout modal, DOM parsing).

ESB uses a checkout modal with shadow DOM selectors. Tour group labels
(Opening, Sunset, etc.) are extracted from section headers rendered
between groups of tour times.

Key data-cy selectors:
  - timeslot: a single tour time row
  - time-label: the time text inside a timeslot
  - time-slot-price: the price text inside a timeslot
  - tour-group-title: section header rendered above each tour group's slots
"""

from .ventrata_base import VentrataBaseScraper, _JS_FIND_IN_SHADOW


class EsbScraper(VentrataBaseScraper):
    """Scrape ESB pricing via checkout modal DOM."""

    venue_label = "ESB"
    product_id = "1708fad0-9198-4809-99e0-6fe16746f0c5"  # ESB 86th Floor GA

    async def _pre_calendar_setup(self, page) -> None:
        """Normalize adult count to exactly 1 before reading the calendar.

        The ESB modal opens with a default quantity (often 2) chosen by the widget.
        The popover time picker shows the TOTAL price for all guests, so we must
        set exactly 1 adult to get per-person pricing.
        """
        for _ in range(10):
            count_text = await page.evaluate(f"""() => {{
                {_JS_FIND_IN_SHADOW}
                const cnt = findInShadow(document, '[data-cy="count"]')[0];
                return cnt ? cnt.textContent.trim() : null;
            }}""")
            try:
                count = int(count_text) if count_text else 0
            except ValueError:
                count = 0

            if count == 1:
                break
            elif count > 1:
                await page.evaluate(f"""() => {{
                    {_JS_FIND_IN_SHADOW}
                    const btn = findInShadow(document, '[data-cy="decrease-button"]')[0];
                    if (btn) btn.click();
                }}""")
            else:
                await page.evaluate(f"""() => {{
                    {_JS_FIND_IN_SHADOW}
                    const btn = findInShadow(document, '[data-cy="increase-button"]')[0];
                    if (btn) btn.click();
                }}""")
            await page.wait_for_timeout(300)

        await page.wait_for_timeout(1000)

    async def _get_tour_times(self, page) -> list[dict]:
        """Read tour times from ESB's Ventrata time picker.

        ESB uses a popover time picker (timePickerType:'select'), same as TOTR.
        Standard [data-cy="timeslot"] list elements are not rendered — slots appear
        as [data-cy="popoverTimeslot-available"] / [data-cy="popoverTimeslot-unavailable"].
        Tour group labels come from [data-cy="tour-group-title"] headers above each group.
        """
        # Try the standard list-based tour times first (Edge-style)
        slots = await super()._get_tour_times(page)
        if slots:
            return slots

        # ESB/TOTR popover picker: read from popoverTimeslot-available / unavailable
        # and capture tour-group-title headers rendered between groups.
        return await page.evaluate(f"""() => {{
            {_JS_FIND_IN_SHADOW}

            const available   = findInShadow(document, '[data-cy="popoverTimeslot-available"]');
            const unavailable = findInShadow(document, '[data-cy="popoverTimeslot-unavailable"]');
            const groupHeaders = findInShadow(document, '[data-cy="tour-group-title"]');

            // Build a map: element → tour group label by DOM position
            // (headers appear above their group's slots in document order)
            function getTourGroup(el) {{
                let best = null;
                for (const h of groupHeaders) {{
                    // header must precede el in document order
                    if (h.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) {{
                        best = h.textContent.trim() || null;
                    }}
                }}
                return best;
            }}

            function parseSlot(el, soldOut) {{
                const text = el.textContent.trim();
                const timeMatch = text.match(/(\\d{{1,2}}:\\d{{2}}\\s*(?:AM|PM))/i);
                if (!timeMatch) return null;
                const timeBase = timeMatch[1];

                // Capture the label between the time and the price (e.g. "Early Access", "Sunset")
                const labelMatch = text.match(/(?:AM|PM)\\s+([A-Za-z][A-Za-z\\s]*)\\s*\\$/i);
                const label = labelMatch ? labelMatch[1].trim() : null;

                // tour_time includes the label for readability in the UI
                const time = label ? timeBase + ' ' + label : timeBase;

                // Use label as tour_group — matches ESB tour group names (Early Access, Sunset, etc.)
                const tourGroup = label || getTourGroup(el) || null;

                const priceMatch = text.match(/(\\$\\d+(?:\\.\\d+)?)/);
                return {{
                    time: time,
                    price_text: priceMatch ? priceMatch[1] : '',
                    sold_out: soldOut,
                    tour_group: tourGroup,
                }};
            }}

            const results = [];
            const seen = new Set();
            for (const el of available) {{
                const slot = parseSlot(el, false);
                if (slot && !seen.has(slot.time)) {{ seen.add(slot.time); results.push(slot); }}
            }}
            for (const el of unavailable) {{
                const slot = parseSlot(el, true);
                if (slot && !seen.has(slot.time)) {{ seen.add(slot.time); results.push(slot); }}
            }}
            return results;
        }}""")
