"""Constants for the Qbus integration."""

from homeassistant.const import Platform

DOMAIN = "qbus"

PLATFORMS: list[str] = [Platform.SWITCH]

CONF_SERIAL = "ctd_serial"
