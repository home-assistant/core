"""The Broadlink integration."""
from dataclasses import dataclass, field

import psutil

from .const import DOMAIN
from .device import BroadlinkDevice
from .discovery import BroadlinkDiscovery
from .helpers import get_broadcast_addrs


@dataclass
class BroadlinkData:
    """Class for sharing data in the Broadlink integration."""

    discovery: BroadlinkDiscovery = None
    config: dict = field(default_factory=dict)
    devices: dict = field(default_factory=dict)
    platforms: dict = field(default_factory=dict)


async def async_setup(hass, config):
    """Set up the Broadlink integration."""
    data = hass.data[DOMAIN] = BroadlinkData()
    nics = await hass.async_add_executor_job(psutil.net_if_addrs)
    data.config["broadcast_addrs"] = get_broadcast_addrs(nics)
    return True


async def async_setup_entry(hass, entry):
    """Set up a Broadlink device from a config entry."""
    data = hass.data[DOMAIN]

    if data.discovery is None:
        data.discovery = BroadlinkDiscovery(hass)
        hass.async_create_task(data.discovery.async_setup())

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
