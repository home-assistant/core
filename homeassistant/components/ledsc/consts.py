"""Constant variables."""

from homeassistant.const import Platform

DOMAIN = "ledsc"
PLATFORMS: list[str] = [Platform.LIGHT]
DEFAULT_HOST = "demo.ledsc.eu"
DEFAULT_PORT = 8443
