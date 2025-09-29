"""Constants for the London underground integration."""

from datetime import timedelta

DOMAIN = "london_underground"

CONF_LINE = "line"

SCAN_INTERVAL = timedelta(seconds=30)

TUBE_LINES = [
    "Bakerloo",
    "Central",
    "Circle",
    "District",
    "DLR",
    "Elizabeth line",
    "Hammersmith & City",
    "Jubilee",
    "Metropolitan",
    "Northern",
    "Piccadilly",
    "Victoria",
    "Waterloo & City",
    "Liberty",
    "Lioness",
    "Mildmay",
    "Suffragette",
    "Weaver",
    "Windrush",
]

# Default lines to monitor if none selected
DEFAULT_LINES = [
    "Bakerloo",
    "Central",
    "Circle",
    "District",
    "DLR",
    "Elizabeth line",
    "Hammersmith & City",
    "Jubilee",
    "Metropolitan",
    "Northern",
    "Piccadilly",
    "Victoria",
    "Waterloo & City",
]
