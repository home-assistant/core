"""Constants for the energieleser integration."""

import logging
from typing import TYPE_CHECKING, Final

from energieleser import DeviceType

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .coordinator import EnergieleserFirmwareCoordinator

DOMAIN: Final = "energieleser"
LOGGER = logging.getLogger(__package__)

FIRMWARE_COORDINATOR: HassKey[EnergieleserFirmwareCoordinator] = HassKey(
    f"{DOMAIN}_firmware_coordinator"
)

# Firmware version is only advertised via the mDNS TXT "version" property, not the
# device API, so it is captured during discovery and stored on the config entry.
CONF_SW_VERSION: Final = "sw_version"

# User-facing product name per device family, shown as the device model and in
# discovery titles. Families without dedicated branding fall back to the raw
# DeviceType value.
DEVICE_MODEL_NAMES: dict[DeviceType, str] = {
    DeviceType.STROMLESER: "stromleser.one",
}


def device_model_name(device_type: DeviceType) -> str:
    """Return the user-facing product name for a device family."""
    return DEVICE_MODEL_NAMES.get(device_type, device_type.value)
