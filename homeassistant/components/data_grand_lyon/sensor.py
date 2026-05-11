"""Sensor platform for the Data Grand Lyon integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from data_grand_lyon_ha import (
    TclPassage,
    TclPassageType,
    VelovAvailabilityLevel,
    VelovStation,
    VelovStationStatus,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SUBENTRY_TYPE_STOP, SUBENTRY_TYPE_VELOV_STATION
from .coordinator import DataGrandLyonConfigEntry, DataGrandLyonCoordinator

PARALLEL_UPDATES = 0

_TZ_PARIS = ZoneInfo("Europe/Paris")

_DEPARTURE_TYPE_OPTIONS = [t.name.lower() for t in TclPassageType]

_STATION_STATUS_OPTIONS = [s.name.lower() for s in VelovStationStatus]

_AVAILABILITY_LEVEL_OPTIONS = [a.name.lower() for a in VelovAvailabilityLevel]


def _departure_time(departure: TclPassage) -> datetime:
    """Return the departure time, localized to Europe/Paris if naive."""
    dt = departure.heure_passage
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_TZ_PARIS)
    return dt


@dataclass(frozen=True, kw_only=True)
class DataGrandLyonStopSensorEntityDescription(SensorEntityDescription):
    """Describes a Data Grand Lyon stop departure sensor entity."""

    departure_index: int
    value_fn: Callable[[TclPassage], StateType | datetime]


STOP_SENSOR_DESCRIPTIONS: tuple[DataGrandLyonStopSensorEntityDescription, ...] = (
    DataGrandLyonStopSensorEntityDescription(
        key="next_departure_1",
        translation_key="next_departure_1",
        device_class=SensorDeviceClass.TIMESTAMP,
        departure_index=0,
        value_fn=_departure_time,
    ),
    DataGrandLyonStopSensorEntityDescription(
        key="next_departure_1_direction",
        translation_key="next_departure_1_direction",
        departure_index=0,
        value_fn=lambda p: p.direction,
    ),
    DataGrandLyonStopSensorEntityDescription(
        key="next_departure_1_type",
        translation_key="next_departure_1_type",
        device_class=SensorDeviceClass.ENUM,
        options=_DEPARTURE_TYPE_OPTIONS,
        departure_index=0,
        value_fn=lambda p: p.type.name.lower(),
    ),
    DataGrandLyonStopSensorEntityDescription(
        key="next_departure_2",
        translation_key="next_departure_2",
        device_class=SensorDeviceClass.TIMESTAMP,
        departure_index=1,
        value_fn=_departure_time,
    ),
    DataGrandLyonStopSensorEntityDescription(
        key="next_departure_2_direction",
        translation_key="next_departure_2_direction",
        departure_index=1,
        value_fn=lambda p: p.direction,
        entity_registry_enabled_default=False,
    ),
    DataGrandLyonStopSensorEntityDescription(
        key="next_departure_2_type",
        translation_key="next_departure_2_type",
        device_class=SensorDeviceClass.ENUM,
        options=_DEPARTURE_TYPE_OPTIONS,
        departure_index=1,
        value_fn=lambda p: p.type.name.lower(),
        entity_registry_enabled_default=False,
    ),
    DataGrandLyonStopSensorEntityDescription(
        key="next_departure_3",
        translation_key="next_departure_3",
        device_class=SensorDeviceClass.TIMESTAMP,
        departure_index=2,
        value_fn=_departure_time,
    ),
    DataGrandLyonStopSensorEntityDescription(
        key="next_departure_3_direction",
        translation_key="next_departure_3_direction",
        departure_index=2,
        value_fn=lambda p: p.direction,
        entity_registry_enabled_default=False,
    ),
    DataGrandLyonStopSensorEntityDescription(
        key="next_departure_3_type",
        translation_key="next_departure_3_type",
        device_class=SensorDeviceClass.ENUM,
        options=_DEPARTURE_TYPE_OPTIONS,
        departure_index=2,
        value_fn=lambda p: p.type.name.lower(),
        entity_registry_enabled_default=False,
    ),
)


@dataclass(frozen=True, kw_only=True)
class DataGrandLyonVelovSensorEntityDescription(SensorEntityDescription):
    """Describes a Data Grand Lyon Vélo'v station sensor entity."""

    value_fn: Callable[[VelovStation], StateType | datetime]


VELOV_SENSOR_DESCRIPTIONS: tuple[DataGrandLyonVelovSensorEntityDescription, ...] = (
    DataGrandLyonVelovSensorEntityDescription(
        key="available_bikes",
        translation_key="available_bikes",
        value_fn=lambda s: s.total_stands.bikes,
    ),
    DataGrandLyonVelovSensorEntityDescription(
        key="available_mechanical_bikes",
        translation_key="available_mechanical_bikes",
        value_fn=lambda s: s.total_stands.mechanical_bikes,
    ),
    DataGrandLyonVelovSensorEntityDescription(
        key="available_electrical_bikes",
        translation_key="available_electrical_bikes",
        value_fn=lambda s: s.total_stands.electrical_bikes,
    ),
    DataGrandLyonVelovSensorEntityDescription(
        key="available_stands",
        translation_key="available_stands",
        value_fn=lambda s: s.total_stands.stands,
    ),
    DataGrandLyonVelovSensorEntityDescription(
        key="station_status",
        translation_key="station_status",
        device_class=SensorDeviceClass.ENUM,
        options=_STATION_STATUS_OPTIONS,
        value_fn=lambda s: s.status.name.lower(),
        entity_registry_enabled_default=False,
    ),
    DataGrandLyonVelovSensorEntityDescription(
        key="availability_level",
        translation_key="availability_level",
        device_class=SensorDeviceClass.ENUM,
        options=_AVAILABILITY_LEVEL_OPTIONS,
        value_fn=lambda s: s.availability.name.lower(),
        entity_registry_enabled_default=False,
    ),
    DataGrandLyonVelovSensorEntityDescription(
        key="capacity",
        translation_key="capacity",
        value_fn=lambda s: s.total_stands.capacity,
        entity_registry_enabled_default=False,
    ),
    DataGrandLyonVelovSensorEntityDescription(
        key="electrical_internal_battery_bikes",
        translation_key="electrical_internal_battery_bikes",
        value_fn=lambda s: s.total_stands.electrical_internal_battery_bikes,
        entity_registry_enabled_default=False,
    ),
    DataGrandLyonVelovSensorEntityDescription(
        key="electrical_removable_battery_bikes",
        translation_key="electrical_removable_battery_bikes",
        value_fn=lambda s: s.total_stands.electrical_removable_battery_bikes,
        entity_registry_enabled_default=False,
    ),
    DataGrandLyonVelovSensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda s: (
            s.last_update
            if s.last_update.tzinfo
            else s.last_update.replace(tzinfo=_TZ_PARIS)
        ),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DataGrandLyonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Data Grand Lyon sensor entities."""
    coordinator = entry.runtime_data

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_STOP):
        async_add_entities(
            (
                DataGrandLyonStopSensor(coordinator, subentry, description)
                for description in STOP_SENSOR_DESCRIPTIONS
            ),
            config_subentry_id=subentry.subentry_id,
        )

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_VELOV_STATION):
        async_add_entities(
            (
                DataGrandLyonVelovSensor(coordinator, subentry, description)
                for description in VELOV_SENSOR_DESCRIPTIONS
            ),
            config_subentry_id=subentry.subentry_id,
        )


class DataGrandLyonStopSensor(
    CoordinatorEntity[DataGrandLyonCoordinator], SensorEntity
):
    """Sensor for Data Grand Lyon stop departures."""

    _attr_has_entity_name = True
    entity_description: DataGrandLyonStopSensorEntityDescription

    def __init__(
        self,
        coordinator: DataGrandLyonCoordinator,
        subentry: ConfigSubentry,
        description: DataGrandLyonStopSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._subentry_id = subentry.subentry_id
        assert subentry.unique_id is not None

        self._attr_unique_id = f"{subentry.unique_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.unique_id)},
            name=subentry.title,
            manufacturer="TCL",
            model="Stop",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _get_departure(self) -> TclPassage | None:
        """Return the departure for this sensor's index, or None."""
        departures = self.coordinator.data.stops.get(self._subentry_id, [])
        index = self.entity_description.departure_index
        if index >= len(departures):
            return None
        return departures[index]

    @property
    def native_value(self) -> StateType | datetime:
        """Return the sensor value."""
        departure = self._get_departure()
        if departure is None:
            return None
        return self.entity_description.value_fn(departure)


class DataGrandLyonVelovSensor(
    CoordinatorEntity[DataGrandLyonCoordinator], SensorEntity
):
    """Sensor for Data Grand Lyon Vélo'v station."""

    _attr_has_entity_name = True
    entity_description: DataGrandLyonVelovSensorEntityDescription

    def __init__(
        self,
        coordinator: DataGrandLyonCoordinator,
        subentry: ConfigSubentry,
        description: DataGrandLyonVelovSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._subentry_id = subentry.subentry_id
        assert subentry.unique_id is not None

        self._attr_unique_id = f"{subentry.unique_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.unique_id)},
            name=subentry.title,
            manufacturer="JCDecaux",
            model="Station",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the sensor value."""
        station = self.coordinator.data.velov_stations.get(self._subentry_id)
        if station is None:
            return None
        return self.entity_description.value_fn(station)
