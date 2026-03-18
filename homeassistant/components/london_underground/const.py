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
    "London Overground",
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
