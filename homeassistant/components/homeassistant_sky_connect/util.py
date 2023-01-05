"""Utility functions for Home Assistant Sky Connect integration."""
from __future__ import annotations

from homeassistant.components import usb
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


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


async def async_is_plugged_in(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Return if the device is plugged in."""
    matcher = usb.USBCallbackMatcher(
        domain=DOMAIN,
        vid=config_entry.data["vid"].upper(),
        pid=config_entry.data["pid"].upper(),
        serial_number=config_entry.data["serial_number"].lower(),
        manufacturer=config_entry.data["manufacturer"].lower(),
        description=config_entry.data["description"].lower(),
    )

    return await usb.async_is_plugged_in(hass, matcher)
