"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from devolo_plc_api.device import Device
from devolo_plc_api.device_api import ConnectedStationInfo, NeighborAPInfo
from devolo_plc_api.plcnet_api import LogicalNetwork

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONNECTED_PLC_DEVICES,
    CONNECTED_WIFI_CLIENTS,
    DOMAIN,
    NEIGHBORING_WIFI_NETWORKS,
)
from .entity import DevoloCoordinatorEntity

_DataT = TypeVar(
    "_DataT",
    bound=LogicalNetwork | list[ConnectedStationInfo] | list[NeighborAPInfo],
)


@dataclass
class DevoloSensorRequiredKeysMixin(Generic[_DataT]):
    """Mixin for required keys."""

    value_func: Callable[[_DataT], int]


@dataclass
class DevoloSensorEntityDescription(
    SensorEntityDescription, DevoloSensorRequiredKeysMixin[_DataT]
):
    """Describes devolo sensor entity."""


SENSOR_TYPES: dict[str, DevoloSensorEntityDescription[Any]] = {
    CONNECTED_PLC_DEVICES: DevoloSensorEntityDescription[LogicalNetwork](
        key=CONNECTED_PLC_DEVICES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:lan",
        value_func=lambda data: len(
            {device.mac_address_from for device in data.data_rates}
        ),
    ),
    CONNECTED_WIFI_CLIENTS: DevoloSensorEntityDescription[list[ConnectedStationInfo]](
        key=CONNECTED_WIFI_CLIENTS,
        icon="mdi:wifi",
        state_class=SensorStateClass.MEASUREMENT,
        value_func=len,
    ),
    NEIGHBORING_WIFI_NETWORKS: DevoloSensorEntityDescription[list[NeighborAPInfo]](
        key=NEIGHBORING_WIFI_NETWORKS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:wifi-marker",
        value_func=len,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device: Device = hass.data[DOMAIN][entry.entry_id]["device"]
    coordinators: dict[str, DataUpdateCoordinator[Any]] = hass.data[DOMAIN][
        entry.entry_id
    ]["coordinators"]

    entities: list[DevoloSensorEntity[Any]] = []
    if device.plcnet:
        entities.append(
            DevoloSensorEntity(
                entry,
                coordinators[CONNECTED_PLC_DEVICES],
                SENSOR_TYPES[CONNECTED_PLC_DEVICES],
                device,
            )
        )
    if device.device and "wifi1" in device.device.features:
        entities.append(
            DevoloSensorEntity(
                entry,
                coordinators[CONNECTED_WIFI_CLIENTS],
                SENSOR_TYPES[CONNECTED_WIFI_CLIENTS],
                device,
            )
        )
        entities.append(
            DevoloSensorEntity(
                entry,
                coordinators[NEIGHBORING_WIFI_NETWORKS],
                SENSOR_TYPES[NEIGHBORING_WIFI_NETWORKS],
                device,
            )
        )
    async_add_entities(entities)


class DevoloSensorEntity(DevoloCoordinatorEntity[_DataT], SensorEntity):
    """Representation of a devolo sensor."""

    entity_description: DevoloSensorEntityDescription[_DataT]

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator[_DataT],
        description: DevoloSensorEntityDescription[_DataT],
        device: Device,
    ) -> None:
        """Initialize entity."""
        self.entity_description = description
        super().__init__(entry, coordinator, device)

    @property
    def native_value(self) -> int:
        """State of the sensor."""
        return self.entity_description.value_func(self.coordinator.data)
