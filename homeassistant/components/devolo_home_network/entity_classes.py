"""General class for all entities."""
from devolo_plc_api.device import Device

from .device import DevoloDevice


class DevoloNetworkOverviewEntity(DevoloDevice):
    """PLC network overview sensor."""

    def __init__(self, device: Device, device_name: str):
        """Initialize entity."""
        super().__init__(device, device_name)
        self._enabled_default = False
        self._icon = "mdi:lan"
        self._name = "Connected PLC devices"
        self._unique_id = f"{self._device.serial_number}_connected_plc_devices"

    async def async_update(self):
        """Update the value async."""
        network_overview = await self._device.plcnet.async_get_network_overview()
        self._state = len(
            {
                device["mac_address_from"]
                for device in network_overview["network"]["data_rates"]
            }
        )

    # TODO add device_state_attributes


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
        network_overview = await self._device.device.async_get_wifi_connected_station()
        self._state = len(network_overview["connected_stations"])

    # TODO add device_state_attributes


class DevoloWifiNetworksEntity(DevoloDevice):
    """Neighboring wifi networks sensor."""

    def __init__(self, device: Device, device_name: str):
        """Initialize entity."""
        super().__init__(device, device_name)
        self._enabled_default = False
        self._icon = "mdi:wifi-marker"
        self._name = "Neighboring wifi networks"
        self._unique_id = f"{self._device.serial_number}_neighboring_wifi_networks"

    async def async_update(self):
        """Update the value async."""
        neighbors = await self._device.device.async_get_wifi_neighbor_access_points()
        self._state = len(neighbors["neighbor_aps"])

    # TODO add device_state_attributes
