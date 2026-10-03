"""Constants for the energieleser integration."""

import logging
from typing import Final

from energieleser import DeviceType

DOMAIN: Final = "energieleser"
LOGGER = logging.getLogger(__package__)

# Firmware version is only advertised via the mDNS TXT "version" property, not the
# device API, so it is captured during discovery and stored on the config entry.
CONF_SW_VERSION: Final = "sw_version"

DEVICE_MODEL_NAMES: dict[DeviceType, str] = {
    DeviceType.STROMLESER: "stromleser.one",
}


def device_model_name(device_type: DeviceType) -> str:
    """Return the user-facing product name for a device family."""
    return DEVICE_MODEL_NAMES.get(device_type, device_type.value)
