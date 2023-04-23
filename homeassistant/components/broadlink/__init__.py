"""The Broadlink integration."""
from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .device import BroadlinkDevice
from .heartbeat import BroadlinkHeartbeat


@dataclass
class BroadlinkData:
    """Class for sharing data within the Broadlink integration."""

    devices: dict[str, BroadlinkDevice] = field(default_factory=dict)
    platforms: dict = field(default_factory=dict)
    heartbeat: BroadlinkHeartbeat | None = None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Broadlink integration."""
    hass.data[DOMAIN] = BroadlinkData()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Broadlink device from a config entry."""
    data: BroadlinkData = hass.data[DOMAIN]

    if data.heartbeat is None:
        data.heartbeat = BroadlinkHeartbeat(hass)
        hass.async_create_task(data.heartbeat.async_setup())

    device = BroadlinkDevice(hass, entry)
    return await device.async_setup()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data: BroadlinkData = hass.data[DOMAIN]

    device = data.devices.pop(entry.entry_id)
    result = await device.async_unload()

    if data.heartbeat and not data.devices:
        await data.heartbeat.async_unload()
        data.heartbeat = None

    return result
