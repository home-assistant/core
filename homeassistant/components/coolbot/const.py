"""Constants for the CoolBot Pro integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "coolbot"

MANUFACTURER: Final = "Store It Cold"

#: How often the coordinator republishes state to Home Assistant.
#:
#: This is not polling the cloud. The client holds an open socket and the device
#: pushes temperatures every 12-15 seconds; this interval only controls how often
#: the already-received state is handed to entities, and doubles as the keepalive
#: cadence. Shorter than the push interval so a new value is never held back.
UPDATE_INTERVAL: Final = timedelta(seconds=10)

#: A device that has not pushed within this window is treated as unavailable,
#: regardless of what the account profile's status field claims.
STALE_AFTER_SECONDS: Final = 120
