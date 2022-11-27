"""Constants for the Min/Max integration."""

from homeassistant.const import Platform

DOMAIN = "min_max"
PLATFORMS = [Platform.SENSOR]

CONF_ENTITY_IDS = "entity_ids"
CONF_ROUND_DIGITS = "round_digits"
