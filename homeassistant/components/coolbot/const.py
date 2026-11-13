"""Constants for the CoolBot Pro integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "coolbot"

MANUFACTURER: Final = "Store It Cold"

#: A device that has not pushed within this window is treated as unavailable,
#: regardless of what the account profile's status field claims.
STALE_AFTER_SECONDS: Final = 120

#: How often the socket is checked and pinged. Readings are not fetched on this
#: schedule: they arrive by push and are published the moment they land. This
#: exists because a long-lived socket has to be kept alive and noticed when it
#: dies, and because staleness is a function of time, so a device that goes
#: silent only becomes unavailable when something re-examines it.
MAINTENANCE_INTERVAL: Final = timedelta(seconds=30)

#: How long a reconnect may take before it counts as failed. A drop is noticed
#: within one maintenance interval, so this keeps a stalled reconnect from
#: holding the last readings on screen past STALE_AFTER_SECONDS.
CONNECT_TIMEOUT_SECONDS: Final = 60

#: How often the account profile is re-read, to notice coolers added to or
#: removed from the account. The profile is otherwise only read on connect, and
#: it is a whole-account document, so this is far longer than the update
#: interval.
PROFILE_REFRESH_INTERVAL: Final = timedelta(minutes=15)
