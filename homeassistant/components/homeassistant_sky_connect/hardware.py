"""The Home Assistant Sky Connect hardware platform."""
from __future__ import annotations

from homeassistant.components.hardware.models import HardwareInfo, USBInfo
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .util import async_is_plugged_in

DONGLE_NAME = "Home Assistant Sky Connect"


async def async_info(hass: HomeAssistant) -> list[HardwareInfo]:
    """Return board info."""
    entries = hass.config_entries.async_entries(DOMAIN)

    return [
        HardwareInfo(
            board=None,
            config_entries=[entry.entry_id],
            dongle=USBInfo(
                vid=entry.data["vid"],
                pid=entry.data["pid"],
                serial_number=entry.data["serial_number"],
                manufacturer=entry.data["manufacturer"],
                description=entry.data["description"],
            ),
            name=DONGLE_NAME,
            url=None,
        )
        for entry in entries
        if await async_is_plugged_in(hass, entry)
    ]
