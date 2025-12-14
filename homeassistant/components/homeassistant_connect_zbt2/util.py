"""Utility functions for Home Assistant Connect ZBT-2 integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.service_info.usb import UsbServiceInfo

_LOGGER = logging.getLogger(__name__)


def get_usb_service_info(config_entry: ConfigEntry) -> UsbServiceInfo:
    """Return UsbServiceInfo."""
    return UsbServiceInfo(
        device=config_entry.data["device"],
        vid=config_entry.data["vid"],
        pid=config_entry.data["pid"],
        serial_number=config_entry.data["serial_number"],
        manufacturer=config_entry.data["manufacturer"],
        description=config_entry.data["product"],
    )
