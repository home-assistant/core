"""Constants for the Sum integration."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "sum"
PLATFORMS = [Platform.SENSOR]

CONF_ENTITY_IDS = "entity_ids"
CONF_ROUND_DIGITS = "round_digits"
