"""Constants for the Overkiz (by Somfy) integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

from pyoverkiz.enums import UIClass
from pyoverkiz.enums.ui import UIWidget

from homeassistant.const import Platform

DOMAIN: Final = "overkiz"

CONF_HUB: Final = "hub"
DEFAULT_HUB: Final = "somfy_europe"

UPDATE_INTERVAL: Final = timedelta(seconds=30)
UPDATE_INTERVAL_ALL_ASSUMED_STATE: Final = timedelta(minutes=60)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

IGNORED_OVERKIZ_DEVICES: list[UIClass | UIWidget] = [
    UIClass.PROTOCOL_GATEWAY,
    UIClass.POD,
]
