"""Constants for the Qbus integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "qbus"
PLATFORMS: list = [Platform.SWITCH]

CONF_ID: Final = "id"
CONF_SERIAL_NUMBER: Final = "serial"
