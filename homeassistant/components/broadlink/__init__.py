"""The Broadlink integration."""
from dataclasses import dataclass, field

from .const import DOMAIN
from .device import BroadlinkDevice


@dataclass
class BroadlinkData:
    """Class for sharing data within the Broadlink integration."""

    devices: dict = field(default_factory=dict)
    platforms: dict = field(default_factory=dict)


async def async_setup(hass, config):
    """Set up the Broadlink integration."""
    hass.data[DOMAIN] = BroadlinkData()
    return True


async def async_setup_entry(hass, entry):
    """Set up a Broadlink device from a config entry."""
    device = BroadlinkDevice(hass, entry)
    return await device.async_setup()


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    device = hass.data[DOMAIN].devices.pop(entry.entry_id)
    return await device.async_unload()
