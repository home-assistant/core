"""Platform for sensor integration."""
from __future__ import annotations

from devolo_plc_api.device import Device

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONNECTED_PLC_DEVICES,
    CONNECTED_WIFI_CLIENTS,
    DOMAIN,
    NEIGHBORING_WIFI_NETWORKS,
)
from .entity import DevoloEntity


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device: Device = hass.data[DOMAIN][entry.entry_id]["device"]
    coordinators: dict[str, DataUpdateCoordinator] = hass.data[DOMAIN][entry.entry_id][
        "coordinators"
    ]

    entities: list[DevoloEntity] = []
    if device.plcnet:
        entities.append(
            DevoloNetworkOverviewEntity(
                coordinators[CONNECTED_PLC_DEVICES], device, entry.title
            )
        )
    if device.device and "wifi1" in device.device.features:
        entities.append(
            DevoloWifiClientsEntity(
                coordinators[CONNECTED_WIFI_CLIENTS], device, entry.title
            )
        )
        entities.append(
            DevoloWifiNetworksEntity(
                coordinators[NEIGHBORING_WIFI_NETWORKS], device, entry.title
            )
        )
    async_add_entities(entities)


class DevoloNetworkOverviewEntity(DevoloEntity, SensorEntity):
    """PLC network overview sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, device: Device, device_name: str
    ) -> None:
        """Initialize entity."""
        self.entity_description = SensorEntityDescription(
            key=CONNECTED_PLC_DEVICES,
            entity_registry_enabled_default=False,
            icon="mdi:lan",
            name="Connected PLC devices",
        )
        super().__init__(coordinator, device, device_name)

    @property
    def native_value(self) -> int:
        """State of the sensor."""
        return len(
            {
                device["mac_address_from"]
                for device in self.coordinator.data["network"]["data_rates"]
            }
        )


class DevoloWifiClientsEntity(DevoloEntity, SensorEntity):
    """Wifi network overview sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, device: Device, device_name: str
    ) -> None:
        """Initialize entity."""
        self.entity_description = SensorEntityDescription(
            key=CONNECTED_WIFI_CLIENTS,
            entity_registry_enabled_default=True,
            icon="mdi:wifi",
            name="Connected Wifi clients",
        )
        super().__init__(coordinator, device, device_name)

    @property
    def native_value(self) -> int:
        """State of the sensor."""
        return len(self.coordinator.data["connected_stations"])


class DevoloWifiNetworksEntity(DevoloEntity, SensorEntity):
    """Neighboring Wifi networks sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, device: Device, device_name: str
    ) -> None:
        """Initialize entity."""
        self.entity_description = SensorEntityDescription(
            key=NEIGHBORING_WIFI_NETWORKS,
            entity_registry_enabled_default=False,
            icon="mdi:wifi-marker",
            name="Neighboring Wifi networks",
        )
        super().__init__(coordinator, device, device_name)

    @property
    def native_value(self) -> int:
        """State of the sensor."""
        return len(self.coordinator.data["neighbor_aps"])
