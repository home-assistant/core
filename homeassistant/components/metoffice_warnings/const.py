"""Constants for the Met Office Weather Warnings integration."""

from datetime import timedelta

DOMAIN = "metoffice_warnings"

CONF_REGION = "region"

SCAN_INTERVAL = timedelta(hours=1)

BASE_URL = (
    "https://weather.metoffice.gov.uk/public/data/PWSCache/WarningsRSS/Region/{region}"
)

REGIONS: dict[str, str] = {
    "os": "Orkney & Shetland",
    "he": "Highland & Eilean Siar",
    "gr": "Grampian",
    "st": "Strathclyde",
    "ta": "Tayside & Fife",
    "dg": "Dumfries, Galloway, Lothian & Borders",
    "ni": "Northern Ireland",
    "wl": "Wales",
    "nw": "North West England",
    "ne": "North East England",
    "yh": "Yorkshire & Humber",
    "wm": "West Midlands",
    "em": "East Midlands",
    "ee": "East of England",
    "sw": "South West England",
    "se": "London & South East England",
    "UK": "UK",
}
