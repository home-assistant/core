"""Constants for CalDAV."""

from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "caldav"
TIMEOUT: Final = 30

# Calendars we have already warned about, keyed by (url, component). This is
# deliberately not stored on a config entry: the warning is per CalDAV server
# and must survive reloads, and the same server may back more than one entry.
WARNED_CALENDARS: HassKey[set[tuple[str, str]]] = HassKey(f"{DOMAIN}_warned_calendars")
