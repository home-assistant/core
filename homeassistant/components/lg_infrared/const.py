"""Constants for the LG IR integration."""

from enum import StrEnum

DOMAIN = "lg_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_DEVICE_TYPE = "device_type"
CONF_CODESET = "codeset"

SIGNAL_LG_TUNER_CHANGED = "lg_ir_tuner_changed"

def tuner_signal(entry_id: str) -> str:
    """Return signal name for tuner updates for a specific config entry."""
    return f"{SIGNAL_LG_TUNER_CHANGED}_{entry_id}"

class LGDeviceType(StrEnum):
    """LG device types."""

    TV = "tv"
