"""Constants for the Marantz IR integration."""

from enum import StrEnum

DOMAIN = "marantz_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_MODEL = "model"


class MarantzModel(StrEnum):
    """Supported Marantz models."""

    GENERIC_AMPLIFIER = "generic_amplifier"
    PM6006 = "pm6006"


# Suffix appended after "Marantz" for the device name and entry title.
MODEL_DISPLAY_NAMES: dict[MarantzModel, str] = {
    MarantzModel.GENERIC_AMPLIFIER: "Amplifier",
    MarantzModel.PM6006: "Amplifier PM6006",
}

# Value written to the device registry's model field. Only models that
# correspond to a specific physical product carry one — generic catch-all
# entries are left without a model ID.
MODEL_IDS: dict[MarantzModel, str] = {
    MarantzModel.PM6006: "PM6006",
}
