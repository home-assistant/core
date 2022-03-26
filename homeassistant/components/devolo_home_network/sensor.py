"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from devolo_plc_api.device import Device

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONNECTED_PLC_DEVICES,
    CONNECTED_WIFI_CLIENTS,
    DOMAIN,
    NEIGHBORING_WIFI_NETWORKS,
)
from .entity import DevoloEntity


@dataclass
class DevoloSensorRequiredKeysMixin:
    """Mixin for required keys."""

    value_func: Callable[[dict[str, Any]], int]


@dataclass
class DevoloSensorEntityDescription(
    SensorEntityDescription, DevoloSensorRequiredKeysMixin
):
    """Describes devolo sensor entity."""


SENSOR_TYPES: dict[str, DevoloSensorEntityDescription] = {
    CONNECTED_PLC_DEVICES: DevoloSensorEntityDescription(
        key=CONNECTED_PLC_DEVICES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:lan",
        name="Connected PLC devices",
        value_func=lambda data: len(
            {device["mac_address_from"] for device in data["network"]["data_rates"]}
        ),
    ),
    CONNECTED_WIFI_CLIENTS: DevoloSensorEntityDescription(
        key=CONNECTED_WIFI_CLIENTS,
        entity_registry_enabled_default=True,
        icon="mdi:wifi",
        name="Connected Wifi clients",
        state_class=SensorStateClass.MEASUREMENT,
        value_func=lambda data: len(data["connected_stations"]),
    ),
    NEIGHBORING_WIFI_NETWORKS: DevoloSensorEntityDescription(
        key=NEIGHBORING_WIFI_NETWORKS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:wifi-marker",
        name="Neighboring Wifi networks",
        value_func=lambda data: len(data["neighbor_aps"]),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device: Device = hass.data[DOMAIN][entry.entry_id]["device"]
    coordinators: dict[str, DataUpdateCoordinator] = hass.data[DOMAIN][entry.entry_id][
        "coordinators"
    ]

    entities: list[DevoloSensorEntity] = []
    if device.plcnet:
        entities.append(
            DevoloSensorEntity(
                coordinators[CONNECTED_PLC_DEVICES],
                SENSOR_TYPES[CONNECTED_PLC_DEVICES],
                device,
                entry.title,
            )
        )
    if device.device and "wifi1" in device.device.features:
        entities.append(
            DevoloSensorEntity(
                coordinators[CONNECTED_WIFI_CLIENTS],
                SENSOR_TYPES[CONNECTED_WIFI_CLIENTS],
                device,
                entry.title,
            )
        )
        entities.append(
            DevoloSensorEntity(
                coordinators[NEIGHBORING_WIFI_NETWORKS],
                SENSOR_TYPES[NEIGHBORING_WIFI_NETWORKS],
                device,
                entry.title,
            )
        )
    async_add_entities(entities)


class DevoloSensorEntity(DevoloEntity, SensorEntity):
    """Representation of a devolo sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: DevoloSensorEntityDescription,
        device: Device,
        device_name: str,
    ) -> None:
        """Initialize entity."""
        self.entity_description: DevoloSensorEntityDescription = description
        super().__init__(coordinator, device, device_name)

    @property
    def native_value(self) -> int:
        """State of the sensor."""
        return self.entity_description.value_func(self.coordinator.data)
