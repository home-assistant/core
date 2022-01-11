"""Constants for the Overkiz (by Somfy) integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Final, Union

from pyoverkiz.enums import UIClass
from pyoverkiz.enums.ui import UIWidget

from homeassistant.const import Platform

DOMAIN: Final = "overkiz"

CONF_HUB: Final = "hub"
DEFAULT_HUB: Final = "somfy_europe"

UPDATE_INTERVAL: Final = timedelta(seconds=30)
UPDATE_INTERVAL_ALL_ASSUMED_STATE: Final = timedelta(minutes=60)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SENSOR,
]

IGNORED_OVERKIZ_DEVICES: list[UIClass | UIWidget] = [
    UIClass.PROTOCOL_GATEWAY,
    UIClass.POD,
]

# Used to map the Somfy widget and ui_class to the Home Assistant platform
OVERKIZ_DEVICE_TO_PLATFORM: dict[UIClass | UIWidget, Platform] = {
    UIClass.DOOR_LOCK: Platform.LOCK,
    UIClass.LIGHT: Platform.LIGHT,
}

OverkizStateType = Union[str, int, float, bool, dict[Any, Any], list[Any], None]
