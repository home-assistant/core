"""The Broadlink integration."""
from dataclasses import dataclass, field

from .const import DOMAIN
from .device import BroadlinkDevice
from .discovery import BroadlinkDiscovery


@dataclass
class BroadlinkData:
    """Class for sharing data in the Broadlink integration."""

    discovery: BroadlinkDiscovery = None
    devices: dict = field(default_factory=dict)
    platforms: dict = field(default_factory=dict)


async def async_setup(hass, config):
    """Set up the Broadlink integration."""
    hass.data[DOMAIN] = BroadlinkData()
    return True


async def async_setup_entry(hass, entry):
    """Set up a Broadlink device from a config entry."""
    data = hass.data[DOMAIN]

    if data.discovery is None:
        data.discovery = BroadlinkDiscovery(hass)
        await data.discovery.async_setup()

    device = BroadlinkDevice(hass, entry)
    return await device.async_setup()


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    data = hass.data[DOMAIN]

    device = data.devices.pop(entry.entry_id)
    result = await device.async_unload()

    if not data.devices:
        await data.discovery.async_unload()
        data.discovery = None

    return result
