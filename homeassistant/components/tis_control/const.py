"""Constants for the TIS Control integration."""

from datetime import timedelta

DOMAIN = "tis_control"


# Modules that announce their changes are updated instantly; the poll only heals missed broadcasts.
POLL_INTERVAL = timedelta(seconds=30)

# Long enough to also catch modules that only show up through their own periodic broadcasts.
DISCOVERY_TIMEOUT = 8.0
