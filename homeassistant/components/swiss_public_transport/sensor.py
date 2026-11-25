"""Support for transport.opendata.ch."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONNECTIONS_COUNT, DOMAIN
from .coordinator import (
    DataConnection,
    DataDeparture,
    SwissPublicTransportConfigEntry,
    SwissPublicTransportStationboardDataUpdateCoordinator,
)

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class SwissPublicTransportSensorEntityDescription[
    _DataT: DataConnection | DataDeparture
](SensorEntityDescription):
    """Describes swiss public transport sensor entity."""

    value_fn: Callable[[_DataT], StateType | datetime]

    index: int = 0


SENSORS: tuple[SwissPublicTransportSensorEntityDescription[DataConnection], ...] = (
    *[
        SwissPublicTransportSensorEntityDescription[DataConnection](
            key=f"departure{i or ''}",
            translation_key=f"departure{i}",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=lambda data_connection: data_connection["departure"],
            index=i,
        )
        for i in range(CONNECTIONS_COUNT)
    ],
    SwissPublicTransportSensorEntityDescription(
        key="duration",
        translation_key="trip_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda data_connection: data_connection["duration"],
    ),
    SwissPublicTransportSensorEntityDescription(
        key="transfers",
        translation_key="transfers",
        value_fn=lambda data_connection: data_connection["transfers"],
    ),
    SwissPublicTransportSensorEntityDescription(
        key="platform",
        translation_key="platform",
        value_fn=lambda data_connection: data_connection["platform"],
    ),
    SwissPublicTransportSensorEntityDescription(
        key="delay",
        translation_key="delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda data_connection: data_connection["delay"],
    ),
    SwissPublicTransportSensorEntityDescription(
        key="line",
        translation_key="line",
        value_fn=lambda data_connection: data_connection["line"],
    ),
)


STATIONBOARD_SENSORS: tuple[
    SwissPublicTransportSensorEntityDescription[DataDeparture], ...
] = (
    *[
        SwissPublicTransportSensorEntityDescription[DataDeparture](
            key=f"departure{i or ''}",
            translation_key=f"departure{i}",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=lambda departure: departure["departure"],
            index=i,
        )
        for i in range(CONNECTIONS_COUNT)
    ],
    SwissPublicTransportSensorEntityDescription[DataDeparture](
        key="destination",
        translation_key="destination",
        value_fn=lambda departure: departure["destination"],
    ),
    SwissPublicTransportSensorEntityDescription[DataDeparture](
        key="platform",
        translation_key="platform",
        value_fn=lambda departure: departure["platform"],
    ),
    SwissPublicTransportSensorEntityDescription[DataDeparture](
        key="delay",
        translation_key="delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda departure: departure["delay"],
    ),
    SwissPublicTransportSensorEntityDescription[DataDeparture](
        key="line",
        translation_key="line",
        value_fn=lambda departure: departure["line"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwissPublicTransportConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry created in the integrations UI."""
    unique_id = config_entry.unique_id

    if TYPE_CHECKING:
        assert unique_id

    coordinator = config_entry.runtime_data
    if isinstance(coordinator, SwissPublicTransportStationboardDataUpdateCoordinator):
        async_add_entities(
            SwissPublicTransportSensor(coordinator, description, unique_id)
            for description in STATIONBOARD_SENSORS
        )
        return

    async_add_entities(
        SwissPublicTransportSensor(coordinator, description, unique_id)
        for description in SENSORS
    )


class SwissPublicTransportSensor[_DataT: DataConnection | DataDeparture](
    CoordinatorEntity[DataUpdateCoordinator[list[_DataT]]], SensorEntity
):
    """Implementation of a Swiss public transport sensor."""

    entity_description: SwissPublicTransportSensorEntityDescription[_DataT]
    _attr_attribution = "Data provided by transport.opendata.ch"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[list[_DataT]],
        entity_description: SwissPublicTransportSensorEntityDescription[_DataT],
        unique_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{unique_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Opendata.ch",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        data = self.coordinator.data
        if len(data) <= self.entity_description.index:
            return None
        return self.entity_description.value_fn(data[self.entity_description.index])
