"""The deako integration."""

from __future__ import annotations

import logging

from pydeako.deako import Deako, DeviceListTimeout, FindDevicesTimeout
from pydeako.discover import DeakoDiscoverer

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]

type DeakoConfigEntry = ConfigEntry[Deako]


async def async_setup_entry(hass: HomeAssistant, entry: DeakoConfigEntry) -> bool:
    """Set up deako."""
    _zc = await zeroconf.async_get_instance(hass)
    discoverer = DeakoDiscoverer(_zc)

    connection = Deako(discoverer.get_address)

    await connection.connect()
    try:
        await connection.find_devices()
    except DeviceListTimeout as exc:  # device list never received
        _LOGGER.warning("Device not responding to device list")
        await connection.disconnect()
        raise ConfigEntryNotReady(exc) from exc
    except FindDevicesTimeout as exc:  # total devices expected not received
        _LOGGER.warning("Device not responding to device requests")
        await connection.disconnect()
        raise ConfigEntryNotReady(exc) from exc

    # If deako devices are advertising on mdns, we should be able to get at least one device
    devices = connection.get_devices()
    if len(devices) == 0:
        await connection.disconnect()
        raise ConfigEntryNotReady(devices)

    entry.runtime_data = connection

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DeakoConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
