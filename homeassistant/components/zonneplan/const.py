"""Constants for the Zonneplan integration."""

from aiozoneinfo import get_time_zone

DOMAIN = "zonneplan"

# It's for Dutchies, so ya...
ZONNEPLAN_TIMEZONE = get_time_zone("Europe/Amsterdam")
