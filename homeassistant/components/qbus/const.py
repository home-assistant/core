"""Constants for the Qbus integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "qbus"
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.SCENE,
    Platform.SWITCH,
]

CONF_SERIAL_NUMBER: Final = "serial"

MANUFACTURER: Final = "Qbus"
