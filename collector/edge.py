"""Edge Hudson Yards scraper (Ventrata modal widget, DOM parsing only)."""

from .ventrata_base import VentrataBaseScraper


class EdgeScraper(VentrataBaseScraper):
    """Scrape Edge Hudson Yards pricing via Ventrata checkout modal DOM."""

    venue_label = "Edge"
    product_id = "5016f498-60f4-4b46-bf08-bc25f9cfae25"  # Edge General Admission
