"""Constants for the Helty Flow integration."""

from datetime import timedelta

DOMAIN = "helty"

#: How often the coordinator polls the unit.
SCAN_INTERVAL = timedelta(seconds=60)

# Fan preset mode identifiers (also used as translation keys).
PRESET_BOOST = "boost"
PRESET_NIGHT = "night"
PRESET_FREE_COOLING = "free_cooling"
