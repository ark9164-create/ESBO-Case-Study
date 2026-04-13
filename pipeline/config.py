"""Attraction definitions, URLs, and ESB pricing reference."""

import os

VENUES = {
    "esb": {
        "name": "Empire State Building",
        "url": "https://www.esbnyc.com/buy-tickets",
    },
    "edge": {
        "name": "Edge Hudson Yards",
        "url": "https://www.edgenyc.com/general-admission-ticket-edge/",
    },
    "summit": {
        "name": "Summit One Vanderbilt",
        "url": "https://tickets.summitov.com/Webstore/shop/viewitems.aspx?CG=sum&C=adm",
    },
    "totr": {
        "name": "Top of the Rock",
        "url": "https://www.rockefellercenter.com/buy-tickets/top-of-the-rock/",
    },
}

# ESB tour group display order (pulled dynamically from Ventrata API tourGroup.title)
# Groups shift time ranges by season, so we don't hardcode times — only display order
ESB_TOUR_GROUP_ORDER = [
    "Early Access",
    "Opening",
    "Pre-Sunset",
    "Pre-Sunset 2",
    "Sunset",
    "Twilight",
    "Post-Sunset 2",
    "Post-Sunset",
    "Last Hour",
]

# Which ESB tour groups count as "sunset" for highlighting
ESB_SUNSET_GROUPS = {"Sunset", "Twilight"}

# Tour time labels shared across attractions
STANDARD_TOUR_TIMES = [
    "9:00 AM", "9:30 AM", "10:00 AM", "10:30 AM",
    "11:00 AM", "11:30 AM", "12:00 PM", "12:30 PM",
    "1:00 PM", "1:30 PM", "2:00 PM", "2:30 PM",
    "3:00 PM", "3:30 PM", "4:00 PM", "4:30 PM",
    "5:00 PM", "5:30 PM", "6:00 PM", "6:30 PM",
    "7:00 PM", "7:30 PM", "8:00 PM", "8:30 PM",
    "9:00 PM", "9:30 PM", "10:00 PM",
]

# US holidays relevant for NYC observation deck pricing
HOLIDAYS = {
    # 2026
    "2026-01-01": "New Year's Day",
    "2026-01-19": "MLK Day",
    "2026-02-16": "Presidents' Day",
    "2026-04-05": "Easter",
    "2026-05-25": "Memorial Day",
    "2026-06-19": "Juneteenth",
    "2026-07-03": "July 4th (Observed)",
    "2026-07-04": "July 4th",
    "2026-09-07": "Labor Day",
    "2026-10-12": "Columbus Day",
    "2026-11-11": "Veterans Day",
    "2026-11-26": "Thanksgiving",
    "2026-11-27": "Black Friday",
    "2026-12-24": "Christmas Eve",
    "2026-12-25": "Christmas",
    "2026-12-31": "New Year's Eve",
    # 2027
    "2027-01-01": "New Year's Day",
    "2027-01-18": "MLK Day",
    "2027-02-15": "Presidents' Day",
    "2027-03-28": "Easter",
    "2027-05-31": "Memorial Day",
    "2027-06-19": "Juneteenth",
    "2027-07-04": "July 4th",
    "2027-07-05": "July 4th (Observed)",
    "2027-09-06": "Labor Day",
    "2027-11-25": "Thanksgiving",
    "2027-11-26": "Black Friday",
    "2027-12-24": "Christmas Eve",
    "2027-12-25": "Christmas",
    "2027-12-31": "New Year's Eve",
}

# Spring break / school vacation weeks (approximate, varies by region)
PEAK_PERIODS = [
    ("2026-03-28", "2026-04-05", "Spring Break"),
    ("2026-06-20", "2026-09-06", "Summer"),
    ("2026-12-19", "2027-01-04", "Holiday Season"),
    ("2027-03-27", "2027-04-04", "Spring Break"),
    ("2027-06-19", "2027-09-05", "Summer"),
]

DB_PATH = os.getenv("PRICE_SHOP_DB_PATH", "data/prices.db")
OUTPUT_DIR = "output"
