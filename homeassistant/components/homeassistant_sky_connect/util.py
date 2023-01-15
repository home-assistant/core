"""Utility functions for Home Assistant Sky Connect integration."""
from __future__ import annotations

from homeassistant.components import usb
from homeassistant.config_entries import ConfigEntry


def get_usb_service_info(config_entry: ConfigEntry) -> usb.UsbServiceInfo:
    """Return UsbServiceInfo."""
    return usb.UsbServiceInfo(
        device=config_entry.data["device"],
        vid=config_entry.data["vid"],
        pid=config_entry.data["pid"],
        serial_number=config_entry.data["serial_number"],
        manufacturer=config_entry.data["manufacturer"],
        description=config_entry.data["description"],
    )
