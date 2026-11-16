"""Constants for the Min/Max integration."""

from enum import StrEnum

DOMAIN = "min_max"

CONF_ENTITY_IDS = "entity_ids"
CONF_ROUND_DIGITS = "round_digits"


class MinMaxEntityStateAttribute(StrEnum):
    """State attributes for min/max entities."""

    ENTITY_ID = "entity_id"
    LAST_ENTITY_ID = "last_entity_id"
    MAX_ENTITY_ID = "max_entity_id"
    MIN_ENTITY_ID = "min_entity_id"
