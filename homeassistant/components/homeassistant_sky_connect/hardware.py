"""The Home Assistant Sky Connect hardware platform."""
from __future__ import annotations

from homeassistant.components.hardware.models import HardwareInfo, USBInfo
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

DONGLE_NAME = "Home Assistant Sky Connect"


@callback
def async_info(hass: HomeAssistant) -> HardwareInfo:
    """Return board info."""
    entries = hass.config_entries.async_entries(DOMAIN)

    dongles = [
        USBInfo(
            vid=entry.data["vid"],
            pid=entry.data["pid"],
            serial_number=entry.data["serial_number"],
            manufacturer=entry.data["manufacturer"],
            description=entry.data["description"],
        )
        for entry in entries
    ]

    return HardwareInfo(
        board=None,
        dongles=dongles,
        name=DONGLE_NAME,
        url=None,
    )
