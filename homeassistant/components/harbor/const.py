"""Constants for the Harbor integration."""

from homeassistant.const import Platform

DOMAIN = "harbor"
MANUFACTURER = "Harbor"
MODEL = "Harbor Camera"

PLATFORMS: list[Platform] = [Platform.SELECT, Platform.SENSOR, Platform.SWITCH]

CONF_CERT_PEM = "cert_pem"
CONF_KEY_PEM = "key_pem"
CONF_SERIAL = "serial"
