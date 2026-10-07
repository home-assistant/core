"""Const for IFTTT."""

from homeassistant.util.hass_dict import HassKey

DOMAIN = "ifttt"

DATA_API_KEYS: HassKey[dict[str, str]] = HassKey(DOMAIN)
