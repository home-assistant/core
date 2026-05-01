"""Constants for the Marantz IR integration."""

from enum import StrEnum

DOMAIN = "marantz_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_MODEL = "model"


class MarantzModel(StrEnum):
    """Supported Marantz models."""

    PM6006 = "pm6006"
