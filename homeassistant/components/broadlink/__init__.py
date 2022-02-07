"""The Broadlink integration."""
from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .device import BroadlinkDevice
from .heartbeat import BroadlinkHeartbeat

CODE_STORAGE_VERSION = 1
FLAG_STORAGE_VERSION = 1


@dataclass
class BroadlinkData:
    """Class for sharing data within the Broadlink integration."""

    devices: dict = field(default_factory=dict)
    platforms: dict = field(default_factory=dict)
    heartbeat: BroadlinkHeartbeat | None = None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Broadlink integration."""
    hass.data[DOMAIN] = BroadlinkData()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Broadlink device from a config entry."""
    data = hass.data[DOMAIN]

    if data.heartbeat is None:
        data.heartbeat = BroadlinkHeartbeat(hass)
        hass.async_create_task(data.heartbeat.async_setup())

    code_storage = Store(
        hass, CODE_STORAGE_VERSION, f"broadlink_remote_{entry.unique_id}_codes"
    )
    flag_storage = Store(
        hass, FLAG_STORAGE_VERSION, f"broadlink_remote_{entry.unique_id}_flags"
    )

    device = BroadlinkDevice(hass, entry, code_storage, flag_storage)
    return await device.async_setup()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data[DOMAIN]

    device = data.devices.pop(entry.entry_id)
    result = await device.async_unload()

    if not data.devices:
        await data.heartbeat.async_unload()
        data.heartbeat = None

    return result
