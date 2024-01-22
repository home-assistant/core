"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Generic, TypeVar

from devolo_plc_api.device import Device
from devolo_plc_api.device_api import ConnectedStationInfo, NeighborAPInfo
from devolo_plc_api.plcnet_api import REMOTE, DataRate, LogicalNetwork

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONNECTED_PLC_DEVICES,
    CONNECTED_WIFI_CLIENTS,
    DOMAIN,
    NEIGHBORING_WIFI_NETWORKS,
    PLC_RX_RATE,
    PLC_TX_RATE,
)
from .entity import DevoloCoordinatorEntity

_CoordinatorDataT = TypeVar(
    "_CoordinatorDataT",
    bound=LogicalNetwork | DataRate | list[ConnectedStationInfo] | list[NeighborAPInfo],
)
_ValueDataT = TypeVar(
    "_ValueDataT",
    bound=LogicalNetwork | DataRate | list[ConnectedStationInfo] | list[NeighborAPInfo],
)


class DataRateDirection(StrEnum):
    """Direction of data transfer."""

    RX = "rx_rate"
    TX = "tx_rate"


@dataclass(frozen=True)
class DevoloSensorRequiredKeysMixin(Generic[_CoordinatorDataT]):
    """Mixin for required keys."""

    value_func: Callable[[_CoordinatorDataT], float]


@dataclass(frozen=True)
class DevoloSensorEntityDescription(
    SensorEntityDescription, DevoloSensorRequiredKeysMixin[_CoordinatorDataT]
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
    PLC_RX_RATE: DevoloSensorEntityDescription[DataRate](
        key=PLC_RX_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="PLC downlink PHY rate",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        value_func=lambda data: getattr(data, DataRateDirection.RX, 0),
        suggested_display_precision=0,
    ),
    PLC_TX_RATE: DevoloSensorEntityDescription[DataRate](
        key=PLC_TX_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="PLC uplink PHY rate",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        value_func=lambda data: getattr(data, DataRateDirection.TX, 0),
        suggested_display_precision=0,
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

    entities: list[BaseDevoloSensorEntity[Any, Any]] = []
    if device.plcnet:
        entities.append(
            DevoloSensorEntity(
                entry,
                coordinators[CONNECTED_PLC_DEVICES],
                SENSOR_TYPES[CONNECTED_PLC_DEVICES],
                device,
            )
        )
        network = await device.plcnet.async_get_network_overview()
        peers = [
            peer.mac_address for peer in network.devices if peer.topology == REMOTE
        ]
        for peer in peers:
            entities.append(
                DevoloPlcDataRateSensorEntity(
                    entry,
                    coordinators[CONNECTED_PLC_DEVICES],
                    SENSOR_TYPES[PLC_TX_RATE],
                    device,
                    peer,
                )
            )
            entities.append(
                DevoloPlcDataRateSensorEntity(
                    entry,
                    coordinators[CONNECTED_PLC_DEVICES],
                    SENSOR_TYPES[PLC_RX_RATE],
                    device,
                    peer,
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


class BaseDevoloSensorEntity(
    Generic[_CoordinatorDataT, _ValueDataT],
    DevoloCoordinatorEntity[_CoordinatorDataT],
    SensorEntity,
):
    """Representation of a devolo sensor."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator[_CoordinatorDataT],
        description: DevoloSensorEntityDescription[_ValueDataT],
        device: Device,
    ) -> None:
        """Initialize entity."""
        self.entity_description = description
        super().__init__(entry, coordinator, device)


class DevoloSensorEntity(BaseDevoloSensorEntity[_CoordinatorDataT, _CoordinatorDataT]):
    """Representation of a generic devolo sensor."""

    entity_description: DevoloSensorEntityDescription[_CoordinatorDataT]

    @property
    def native_value(self) -> float:
        """State of the sensor."""
        return self.entity_description.value_func(self.coordinator.data)


class DevoloPlcDataRateSensorEntity(BaseDevoloSensorEntity[LogicalNetwork, DataRate]):
    """Representation of a devolo PLC data rate sensor."""

    entity_description: DevoloSensorEntityDescription[DataRate]

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator[LogicalNetwork],
        description: DevoloSensorEntityDescription[DataRate],
        device: Device,
        peer: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(entry, coordinator, description, device)
        self._peer = peer
        peer_device = next(
            device
            for device in self.coordinator.data.devices
            if device.mac_address == peer
        )

        self._attr_unique_id = f"{self._attr_unique_id}_{peer}"
        self._attr_name = f"{description.name} ({peer_device.user_device_name})"
        self._attr_entity_registry_enabled_default = peer_device.attached_to_router

    @property
    def native_value(self) -> float:
        """State of the sensor."""
        return self.entity_description.value_func(
            next(
                data_rate
                for data_rate in self.coordinator.data.data_rates
                if data_rate.mac_address_from == self.device.mac
                and data_rate.mac_address_to == self._peer
            )
        )
