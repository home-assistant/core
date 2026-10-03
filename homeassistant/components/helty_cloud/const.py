"""Constants for the Helty Flow Cloud integration."""

from datetime import timedelta

DOMAIN = "helty_cloud"

#: How often the coordinator reads the cloud. The poll only reads the last
#: message the panel sent, it does not wake the panel: the manufacturer asks
#: not to solicit the panel on a short timer, and the panel reports on its
#: own about every five minutes anyway.
SCAN_INTERVAL = timedelta(minutes=5)

# Fan preset mode identifiers (also used as translation keys).
PRESET_BOOST = "boost"
PRESET_NIGHT = "night"
PRESET_FREE_COOLING = "free_cooling"
