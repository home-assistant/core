"""Constants for the Qbus integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "qbus"
PLATFORMS: list = [Platform.SWITCH]

CONF_ID: Final = "id"
CONF_SERIAL: Final = "serial"

DATA_QBUS_CONFIG: Final = "QBUS_CONFIG"
DATA_QBUS_CONFIG_EVENT: Final = "QBUS_CONFIG_EVENT"
