"""The Gree Climate integration."""

from datetime import timedelta
import logging

from greeclimate.device import Device, DeviceInfo
from greeclimate.discovery import Discovery, Listener
from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError

from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DISCOVERY_SCAN_INTERVAL,
    DISCOVERY_TIMEOUT,
    DISPATCH_DEVICE_DISCOVERED,
)
from .coordinator import DeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SWITCH]

type GreeConfigEntry = ConfigEntry[list[DeviceDataUpdateCoordinator]]


async def async_setup_entry(hass: HomeAssistant, entry: GreeConfigEntry) -> bool:
    """Set up Gree Climate from a config entry."""
    gree_discovery = DiscoveryService(hass, entry)

    async def _async_scan_update(_=None):
        bcast_addr = list(await async_get_ipv4_broadcast_addresses(hass))
        await gree_discovery.discovery.scan(0, bcast_ifaces=bcast_addr)

    entry.runtime_data = []

    _LOGGER.debug("Scanning network for Gree devices")
    await _async_scan_update()

    entry.async_on_unload(
        async_track_time_interval(
            hass, _async_scan_update, timedelta(seconds=DISCOVERY_SCAN_INTERVAL)
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GreeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class DiscoveryService(Listener):
    """Discovery event handler for gree devices."""

    def __init__(self, hass: HomeAssistant, entry: GreeConfigEntry) -> None:
        """Initialize discovery service."""
        super().__init__()
        self.hass = hass
        self.entry = entry

        self.discovery = Discovery(DISCOVERY_TIMEOUT)
        self.discovery.add_listener(self)

    async def device_found(self, device_info: DeviceInfo) -> None:
        """Handle new device found on the network."""

        device = Device(device_info)
        try:
            await device.bind()
        except DeviceNotBoundError:
            _LOGGER.error("Unable to bind to gree device: %s", device_info)
        except DeviceTimeoutError:
            _LOGGER.error("Timeout trying to bind to gree device: %s", device_info)

        _LOGGER.debug(
            "Adding Gree device %s at %s:%i",
            device.device_info.name,
            device.device_info.ip,
            device.device_info.port,
        )
        coordo = DeviceDataUpdateCoordinator(self.hass, device)
        self.entry.runtime_data.append(coordo)
        await coordo.async_refresh()

        async_dispatcher_send(self.hass, DISPATCH_DEVICE_DISCOVERED, coordo)

    async def device_update(self, device_info: DeviceInfo) -> None:
        """Handle updates in device information, update if ip has changed."""
        for coordinator in self.entry.runtime_data:
            if coordinator.device.device_info.mac == device_info.mac:
                coordinator.device.device_info.ip = device_info.ip
                await coordinator.async_refresh()
