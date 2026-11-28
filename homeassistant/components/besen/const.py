"""Constants for the Besen integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "besen"
CONF_TRANSPORT: Final = "transport"
CONF_SERIAL: Final = "serial"
TRANSPORT_BLUETOOTH: Final = "bluetooth"
TRANSPORT_LAN: Final = "lan"
NAME: Final = "Besen"

PLATFORMS: Final = [Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]
