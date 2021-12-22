"""Constants for the Overkiz (by Somfy) integration."""
from datetime import timedelta
from typing import Final, List

from pyoverkiz.enums import UIClass

from homeassistant.const import Platform

DOMAIN: Final = "tahoma"

CONF_HUB: Final = "hub"
DEFAULT_HUB: Final = "somfy_europe"

UPDATE_INTERVAL: Final = timedelta(seconds=30)
UPDATE_INTERVAL_ALL_ASSUMED_STATE: Final = timedelta(minutes=60)

SUPPORTED_PLATFORMS: List[str] = [
    Platform.SENSOR,
]

IGNORED_OVERKIZ_DEVICES: List[str] = [
    UIClass.PROTOCOL_GATEWAY,
    UIClass.POD,
]
