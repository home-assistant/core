"""Utility functions for Home Assistant SkyConnect integration."""

from __future__ import annotations

import logging

from homeassistant.components import usb
from homeassistant.components.homeassistant_hardware.util import ApplicationType
from homeassistant.config_entries import ConfigEntry

from .const import HardwareVariant

_LOGGER = logging.getLogger(__name__)

FW_TYPE_NAMES = {
    ApplicationType.EZSP: "Zigbee",
    ApplicationType.SPINEL: "Thread",
    ApplicationType.CPC: "Multiprotocol",
}


def get_usb_service_info(config_entry: ConfigEntry) -> usb.UsbServiceInfo:
    """Return UsbServiceInfo."""
    return usb.UsbServiceInfo(
        device=config_entry.data["device"],
        vid=config_entry.data["vid"],
        pid=config_entry.data["pid"],
        serial_number=config_entry.data["serial_number"],
        manufacturer=config_entry.data["manufacturer"],
        description=config_entry.data["product"],
    )


def get_hardware_variant(config_entry: ConfigEntry) -> HardwareVariant:
    """Get the hardware variant from the config entry."""
    return HardwareVariant.from_usb_product_name(config_entry.data["product"])


def create_entry_title(
    entry: ConfigEntry, firmware_type: ApplicationType | None = None
) -> str:
    """Create a title for the config entry, incorporating the firmware type."""
    hw_variant = get_hardware_variant(entry)

    if firmware_type is None:
        firmware_type = ApplicationType(entry.data["firmware"])

    if firmware_type not in FW_TYPE_NAMES:
        return hw_variant.full_name

    return f"{hw_variant.full_name} ({FW_TYPE_NAMES[firmware_type]})"
