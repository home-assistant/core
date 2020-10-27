"""The Broadlink integration."""
from dataclasses import dataclass, field

from .const import DOMAIN
from .device import BroadlinkDevice
from .discovery import BroadlinkScout


@dataclass
class BroadlinkData:
    """Class for sharing data within the Broadlink integration."""

    config: dict = None
    discovery: BroadlinkScout = None
    devices: dict = field(default_factory=dict)
    platforms: dict = field(default_factory=dict)


async def async_setup(hass, config):
    """Set up the Broadlink integration."""
    config = config.get(DOMAIN)
    discovery = BroadlinkScout(hass)
    hass.data[DOMAIN] = BroadlinkData(config, discovery)
    await discovery.async_start()
    return True


async def async_setup_entry(hass, entry):
    """Set up a Broadlink device from a config entry."""
    discovery = hass.data[DOMAIN].discovery
    if not discovery.is_on:
        await discovery.async_start()

    device = BroadlinkDevice(hass, entry)
    return await device.async_setup()


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    config = hass.data[DOMAIN].config
    discovery = hass.data[DOMAIN].discovery
    devices = hass.data[DOMAIN].devices

    device = devices.pop(entry.entry_id)
    result = await device.async_unload()

    if not devices and config is None:
        await discovery.async_stop()

    return result
