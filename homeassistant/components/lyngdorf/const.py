"""Constants for the Lyngdorf integration."""

from homeassistant.const import Platform

DOMAIN = "lyngdorf"
DEFAULT_DEVICE_NAME = "Lyngdorf"

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]
CONF_SERIAL_NUMBER = "serial_number"
