"""Constants for OwnTracks."""

from typing import Any, Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "owntracks"

DATA_OWNTRACKS_CONFIG: HassKey[dict[str, Any]] = HassKey(DOMAIN)

ATTR_ADDRESS: Final = "address"
ATTR_BATTERY_STATUS: Final = "battery_status"
ATTR_COURSE: Final = "course"
ATTR_TID: Final = "tid"
ATTR_UPDATE_TIMESTAMP: Final = "update_timestamp"
ATTR_VELOCITY: Final = "velocity"
