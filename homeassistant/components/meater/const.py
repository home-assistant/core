"""Constants for the Meater Temperature Probe integration."""

from homeassistant.util.hass_dict import HassKey

DOMAIN = "meater"

MEATER_DATA: HassKey[set[str]] = HassKey(DOMAIN)
