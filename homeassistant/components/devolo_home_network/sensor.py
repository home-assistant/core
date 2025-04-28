"""Platform for sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from devolo_plc_api.device_api import ConnectedStationInfo, NeighborAPInfo
from devolo_plc_api.plcnet_api import REMOTE, DataRate, LogicalNetwork

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow

from . import DevoloHomeNetworkConfigEntry
from .const import (
    CONNECTED_PLC_DEVICES,
    CONNECTED_WIFI_CLIENTS,
    LAST_RESTART,
    NEIGHBORING_WIFI_NETWORKS,
    PLC_RX_RATE,
    PLC_TX_RATE,
)
from .coordinator import DevoloDataUpdateCoordinator
from .entity import DevoloCoordinatorEntity

PARALLEL_UPDATES = 0


def _last_restart(runtime: int) -> datetime:
    """Calculate uptime. As fetching the data might also take some time, let's floor to the nearest 5 seconds."""
    now = utcnow()
    return (
        now
        - timedelta(seconds=runtime)
        - timedelta(seconds=(now.timestamp() - runtime) % 5)
    )


type _CoordinatorDataType = (
    LogicalNetwork | DataRate | list[ConnectedStationInfo] | list[NeighborAPInfo] | int
)
type _SensorDataType = int | float | datetime


class DataRateDirection(StrEnum):
    """Direction of data transfer."""

    RX = "rx_rate"
    TX = "tx_rate"


@dataclass(frozen=True, kw_only=True)
class DevoloSensorEntityDescription[
    _CoordinatorDataT: _CoordinatorDataType,
    _SensorDataT: _SensorDataType,
](SensorEntityDescription):
    """Describes devolo sensor entity."""

    value_func: Callable[[_CoordinatorDataT], _SensorDataT]


SENSOR_TYPES: dict[str, DevoloSensorEntityDescription[Any, Any]] = {
    CONNECTED_PLC_DEVICES: DevoloSensorEntityDescription[LogicalNetwork, int](
        key=CONNECTED_PLC_DEVICES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_func=lambda data: len(
            {device.mac_address_from for device in data.data_rates}
        ),
    ),
    CONNECTED_WIFI_CLIENTS: DevoloSensorEntityDescription[
        list[ConnectedStationInfo], int
    ](
        key=CONNECTED_WIFI_CLIENTS,
        state_class=SensorStateClass.MEASUREMENT,
        value_func=len,
    ),
    NEIGHBORING_WIFI_NETWORKS: DevoloSensorEntityDescription[list[NeighborAPInfo], int](
        key=NEIGHBORING_WIFI_NETWORKS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_func=len,
    ),
    PLC_RX_RATE: DevoloSensorEntityDescription[DataRate, float](
        key=PLC_RX_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="PLC downlink PHY rate",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        value_func=lambda data: getattr(data, DataRateDirection.RX, 0),
        suggested_display_precision=0,
    ),
    PLC_TX_RATE: DevoloSensorEntityDescription[DataRate, float](
        key=PLC_TX_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="PLC uplink PHY rate",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        value_func=lambda data: getattr(data, DataRateDirection.TX, 0),
        suggested_display_precision=0,
    ),
    LAST_RESTART: DevoloSensorEntityDescription[int, datetime](
        key=LAST_RESTART,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_func=_last_restart,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DevoloHomeNetworkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device = entry.runtime_data.device
    coordinators = entry.runtime_data.coordinators

    entities: list[BaseDevoloSensorEntity[Any, Any, Any]] = []
    if device.plcnet:
        entities.append(
            DevoloSensorEntity(
                entry,
                coordinators[CONNECTED_PLC_DEVICES],
                SENSOR_TYPES[CONNECTED_PLC_DEVICES],
            )
        )
        network: LogicalNetwork = coordinators[CONNECTED_PLC_DEVICES].data
        peers = [
            peer.mac_address for peer in network.devices if peer.topology == REMOTE
        ]
        for peer in peers:
            entities.append(
                DevoloPlcDataRateSensorEntity(
                    entry,
                    coordinators[CONNECTED_PLC_DEVICES],
                    SENSOR_TYPES[PLC_TX_RATE],
                    peer,
                )
            )
            entities.append(
                DevoloPlcDataRateSensorEntity(
                    entry,
                    coordinators[CONNECTED_PLC_DEVICES],
                    SENSOR_TYPES[PLC_RX_RATE],
                    peer,
                )
            )
    if device.device and "restart" in device.device.features:
        entities.append(
            DevoloSensorEntity(
                entry,
                coordinators[LAST_RESTART],
                SENSOR_TYPES[LAST_RESTART],
            )
        )
    if device.device and "wifi1" in device.device.features:
        entities.append(
            DevoloSensorEntity(
                entry,
                coordinators[CONNECTED_WIFI_CLIENTS],
                SENSOR_TYPES[CONNECTED_WIFI_CLIENTS],
            )
        )
        entities.append(
            DevoloSensorEntity(
                entry,
                coordinators[NEIGHBORING_WIFI_NETWORKS],
                SENSOR_TYPES[NEIGHBORING_WIFI_NETWORKS],
            )
        )
    async_add_entities(entities)


class BaseDevoloSensorEntity[
    _CoordinatorDataT: _CoordinatorDataType,
    _ValueDataT: _CoordinatorDataType,
    _SensorDataT: _SensorDataType,
](
    DevoloCoordinatorEntity[_CoordinatorDataT],
    SensorEntity,
):
    """Representation of a devolo sensor."""

    def __init__(
        self,
        entry: DevoloHomeNetworkConfigEntry,
        coordinator: DevoloDataUpdateCoordinator[_CoordinatorDataT],
        description: DevoloSensorEntityDescription[_ValueDataT, _SensorDataT],
    ) -> None:
        """Initialize entity."""
        self.entity_description = description
        super().__init__(entry, coordinator)


class DevoloSensorEntity[
    _CoordinatorDataT: _CoordinatorDataType,
    _ValueDataT: _CoordinatorDataType,
    _SensorDataT: _SensorDataType,
](BaseDevoloSensorEntity[_CoordinatorDataT, _ValueDataT, _SensorDataT]):
    """Representation of a generic devolo sensor."""

    entity_description: DevoloSensorEntityDescription[_CoordinatorDataT, _SensorDataT]

    @property
    def native_value(self) -> int | float | datetime:
        """State of the sensor."""
        return self.entity_description.value_func(self.coordinator.data)


class DevoloPlcDataRateSensorEntity(
    BaseDevoloSensorEntity[LogicalNetwork, DataRate, float]
):
    """Representation of a devolo PLC data rate sensor."""

    entity_description: DevoloSensorEntityDescription[DataRate, float]

    def __init__(
        self,
        entry: DevoloHomeNetworkConfigEntry,
        coordinator: DevoloDataUpdateCoordinator[LogicalNetwork],
        description: DevoloSensorEntityDescription[DataRate, float],
        peer: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(entry, coordinator, description)
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
