"""Constants for the CoolBot Pro integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "coolbot"

MANUFACTURER: Final = "Store It Cold"

#: How often already-received client state is handed to entities; doubles as the
#: keepalive cadence. The cloud pushes every 12-15 seconds; this never polls it.
UPDATE_INTERVAL: Final = timedelta(seconds=10)

#: A device that has not pushed within this window is treated as unavailable,
#: regardless of what the account profile's status field claims.
STALE_AFTER_SECONDS: Final = 120
