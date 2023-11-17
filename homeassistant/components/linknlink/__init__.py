"""The linknlink integration."""
from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .device import LinknLinkDevice
from .heartbeat import LinknLinkHeartbeat

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class linknlinkData:
    """Class for sharing data within the linknlink integration."""

    devices: dict[str, LinknLinkDevice] = field(default_factory=dict)
    platforms: dict = field(default_factory=dict)
    heartbeat: LinknLinkHeartbeat | None = None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the linknlink integration."""
    hass.data[DOMAIN] = linknlinkData()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a linknlink device from a config entry."""
    data: linknlinkData = hass.data[DOMAIN]

    device = LinknLinkDevice(hass, entry)
    if not await device.async_setup():
        return False
    if data.heartbeat is None:
        data.heartbeat = LinknLinkHeartbeat(hass)
        hass.async_create_task(data.heartbeat.async_setup())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data: linknlinkData = hass.data[DOMAIN]

    device = data.devices.pop(entry.entry_id)
    result = await device.async_unload()

    if data.heartbeat and not data.devices:
        await data.heartbeat.async_unload()
        data.heartbeat = None

    return result
