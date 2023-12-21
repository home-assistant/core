"""The linknlink integration."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .device import LinknLinkDevice
from .heartbeat import LinknLinkHeartbeat

_LOGGER = logging.getLogger(__name__)


@dataclass
class linknlinkData:
    """Class for sharing data within the linknlink integration."""

    devices: dict[str, LinknLinkDevice] = field(default_factory=dict)
    platforms: dict = field(default_factory=dict)
    heartbeat: LinknLinkHeartbeat | None = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a linknlink device from a config entry."""
    if not hass.data.get(DOMAIN):
        hass.data[DOMAIN] = linknlinkData()
    data: linknlinkData = hass.data[DOMAIN]

    device = LinknLinkDevice(hass, entry)
    if not await device.async_setup():
        _LOGGER.error(
            "Unable to setup linknlink device - config=%s", device.config.data
        )
        raise ConfigEntryNotReady
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
