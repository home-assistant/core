"""General classes for all entities."""
from datetime import timedelta

from devolo_plc_api.device import Device
from devolo_plc_api.exceptions.device import DeviceUnavailable

from homeassistant.util import Throttle

from .device import DevoloDevice

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)


class DevoloNetworkOverviewEntity(DevoloDevice):
    """PLC network overview sensor."""

    def __init__(self, device: Device, device_name: str):
        """Initialize entity."""
        super().__init__(device, device_name)
        self._enabled_default = False
        self._icon = "mdi:lan"
        self._name = "Connected PLC devices"
        self._unique_id = f"{self._device.serial_number}_connected_plc_devices"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update the value async."""
        try:
            network_overview = await self._device.plcnet.async_get_network_overview()
            self._state = len(
                {
                    device["mac_address_from"]
                    for device in network_overview["network"]["data_rates"]
                }
            )
            self._set_availablility(True)
        except DeviceUnavailable:
            self._set_availablility(False)


class DevoloWifiClientsEntity(DevoloDevice):
    """Wifi network overview sensor."""

    def __init__(self, device: Device, device_name: str):
        """Initialize entity."""
        super().__init__(device, device_name)
        self._enabled_default = True
        self._icon = "mdi:wifi"
        self._name = "Connected wifi clients"
        self._unique_id = f"{self._device.serial_number}_connected_wifi_clients"

    async def async_update(self):
        """Update the value async."""
        try:
            network_overview = (
                await self._device.device.async_get_wifi_connected_station()
            )
            self._state = len(network_overview["connected_stations"])
            self._set_availablility(True)
        except DeviceUnavailable:
            self._set_availablility(False)


class DevoloWifiNetworksEntity(DevoloDevice):
    """Neighboring wifi networks sensor."""

    def __init__(self, device: Device, device_name: str):
        """Initialize entity."""
        super().__init__(device, device_name)
        self._enabled_default = False
        self._icon = "mdi:wifi-marker"
        self._name = "Neighboring wifi networks"
        self._unique_id = f"{self._device.serial_number}_neighboring_wifi_networks"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update the value async."""
        try:
            neighbors = (
                await self._device.device.async_get_wifi_neighbor_access_points()
            )
            self._state = len(neighbors["neighbor_aps"])
            self._set_availablility(True)
        except DeviceUnavailable:
            self._set_availablility(False)
