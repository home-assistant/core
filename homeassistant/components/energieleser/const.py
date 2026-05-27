"""Constants for the energieleser integration."""

import logging
from typing import Final

from energieleser import DeviceType

DOMAIN: Final = "energieleser"
LOGGER = logging.getLogger(__package__)

# User-facing product name per device family, shown as the device model and in
# discovery titles. Families without dedicated branding fall back to the raw
# DeviceType value.
DEVICE_MODEL_NAMES: dict[DeviceType, str] = {
    DeviceType.STROMLESER: "stromleser.one",
}


def device_model_name(device_type: DeviceType) -> str:
    """Return the user-facing product name for a device family."""
    return DEVICE_MODEL_NAMES.get(device_type, device_type.value)
