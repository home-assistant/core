"""Constants for the Prowl Notification service."""

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

DOMAIN = "prowl"
PLATFORMS = [Platform.NOTIFY]

CONF_ENTRY = "entry"
CONF_SETUP = "setup"
# Current legacy notify setup per imported entry; only that setup may register
DATA_LEGACY_SETUPS: HassKey[dict[str, object]] = HassKey(f"{DOMAIN}_legacy_setups")
CONF_LEGACY_SERVICE_NAME = "legacy_service_name"
CONF_NAMES = "names"

PRIORITY_MAP: dict[str, int] = {
    "very_low": -2,
    "moderate": -1,
    "normal": 0,
    "high": 1,
    "emergency": 2,
}
