"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta

from devolo_plc_api.device import Device
from devolo_plc_api.exceptions.device import DeviceUnavailable

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import Throttle

from .const import DOMAIN
from .entity import DevoloEntity

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=15)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device = hass.data[DOMAIN][entry.entry_id]
    plc_entities = [DevoloNetworkOverviewEntity]
    wifi_entities = [DevoloWifiClientsEntity, DevoloWifiNetworksEntity]

    entities: list[DevoloEntity] = []
    for plc_entity in plc_entities:
        entities.append(plc_entity(device, entry.title))
    if "wifi1" in device.device.features:
        for wifi_entity in wifi_entities:
            entities.append(wifi_entity(device, entry.title))
    async_add_entities(entities)


class DevoloNetworkOverviewEntity(DevoloEntity):
    """PLC network overview sensor."""

    def __init__(self, device: Device, device_name: str) -> None:
        """Initialize entity."""
        super().__init__(device, device_name)
        self._attr_entity_registry_enabled_default = False
        self._attr_icon = "mdi:lan"
        self._attr_name = "Connected PLC devices"
        self._attr_unique_id = f"{self._device.serial_number}_connected_plc_devices"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Update the value async."""
        try:
            network_overview = await self._device.plcnet.async_get_network_overview()
            self._attr_state = len(
                {
                    device["mac_address_from"]
                    for device in network_overview["network"]["data_rates"]
                }
            )
            self._set_availability(True)
        except DeviceUnavailable:
            self._set_availability(False)


class DevoloWifiClientsEntity(DevoloEntity):
    """Wifi network overview sensor."""

    def __init__(self, device: Device, device_name: str) -> None:
        """Initialize entity."""
        super().__init__(device, device_name)
        self._attr_entity_registry_enabled_default = True
        self._attr_icon = "mdi:wifi"
        self._attr_name = "Connected wifi clients"
        self._attr_unique_id = f"{self._device.serial_number}_connected_wifi_clients"

    async def async_update(self) -> None:
        """Update the value async."""
        try:
            network_overview = (
                await self._device.device.async_get_wifi_connected_station()
            )
            self._attr_state = len(network_overview["connected_stations"])
            self._set_availability(True)
        except DeviceUnavailable:
            self._set_availability(False)


class DevoloWifiNetworksEntity(DevoloEntity):
    """Neighboring wifi networks sensor."""

    def __init__(self, device: Device, device_name: str) -> None:
        """Initialize entity."""
        super().__init__(device, device_name)
        self._attr_entity_registry_enabled_default = False
        self._attr_icon = "mdi:wifi-marker"
        self._attr_name = "Neighboring wifi networks"
        self._attr_unique_id = f"{self._device.serial_number}_neighboring_wifi_networks"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Update the value async."""
        try:
            neighbors = (
                await self._device.device.async_get_wifi_neighbor_access_points()
            )
            self._attr_state = len(neighbors["neighbor_aps"])
            self._set_availability(True)
        except DeviceUnavailable:
            self._set_availability(False)
