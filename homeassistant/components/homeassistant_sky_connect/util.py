"""Utility functions for Home Assistant SkyConnect integration."""

from __future__ import annotations

import logging

from homeassistant.components import usb
from homeassistant.config_entries import ConfigEntry

from .const import HardwareVariant

_LOGGER = logging.getLogger(__name__)


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
