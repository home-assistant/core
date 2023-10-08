"""Helper and wrapper classes for refoss module."""
from __future__ import annotations

from datetime import timedelta
import logging

from refoss_ha.controller.device import BaseDevice
from refoss_ha.device import DeviceInfo
from refoss_ha.device_manager import async_build_base_device
from refoss_ha.discovery import Discovery, Listener

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COORDINATORS, DISPATCH_DEVICE_DISCOVERED, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """Manages polling for state changes from the device."""

    def __init__(self, hass: HomeAssistant, device: BaseDevice) -> None:
        """Initialize the data update coordinator."""
        DataUpdateCoordinator.__init__(
            self,
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{device.device_info.dev_name}",
            update_interval=timedelta(seconds=15),
        )
        self.device = device

    async def _async_update_data(self):
        """Update the state of the device."""
        await self.device.async_handle_update()


class DiscoveryService(Listener):
    """Discovery event handler for refoss devices."""

    def __init__(self, hass: HomeAssistant, discovery: Discovery) -> None:
        """Initialize discovery service."""
        super().__init__()
        self.hass = hass

        self.discovery = discovery
        self.discovery.add_listener(self)

        hass.data[DOMAIN].setdefault(COORDINATORS, [])

    async def device_found(self, device_info: DeviceInfo) -> None:
        """Handle new device found on the network."""

        device = await async_build_base_device(device_info)
        if device is None:
            return None

        coordo = DeviceDataUpdateCoordinator(self.hass, device)
        self.hass.data[DOMAIN][COORDINATORS].append(coordo)
        await coordo.async_refresh()

        async_dispatcher_send(self.hass, DISPATCH_DEVICE_DISCOVERED, coordo)

    async def device_update(self, device_info: DeviceInfo) -> None:
        """Handle updates in device information, update if ip has changed."""
        for coordinator in self.hass.data[DOMAIN][COORDINATORS]:
            if coordinator.device.device_info.mac == device_info.mac:
                coordinator.device.device_info.inner_ip = device_info.inner_ip
                await coordinator.async_refresh()
