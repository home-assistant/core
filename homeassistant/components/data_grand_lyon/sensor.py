"""Sensor platform for the Data Grand Lyon integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override
from zoneinfo import ZoneInfo

from data_grand_lyon_ha import TclParkAndRide, TclPassage, TclPassageType, VelovStation

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    SUBENTRY_TYPE_PARK_AND_RIDE,
    SUBENTRY_TYPE_STOP,
    SUBENTRY_TYPE_VELOV_STATION,
)
from .coordinator import DataGrandLyonConfigEntry
from .entity import (
    DataGrandLyonParkAndRideEntity,
    DataGrandLyonTclEntity,
    DataGrandLyonVelovEntity,
)

PARALLEL_UPDATES = 0

_TZ_PARIS = ZoneInfo("Europe/Paris")

_DEPARTURE_TYPE_OPTIONS = [t.name.lower() for t in TclPassageType]


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
)


@dataclass(frozen=True, kw_only=True)
class DataGrandLyonParkAndRideSensorEntityDescription(SensorEntityDescription):
    """Describes a Data Grand Lyon park-and-ride sensor entity."""

    value_fn: Callable[[TclParkAndRide], StateType]


PARK_AND_RIDE_SENSOR_DESCRIPTIONS: tuple[
    DataGrandLyonParkAndRideSensorEntityDescription, ...
] = (
    DataGrandLyonParkAndRideSensorEntityDescription(
        key="available_spaces",
        translation_key="available_spaces",
        value_fn=lambda p: p.nb_tot_place_dispo,
    ),
    DataGrandLyonParkAndRideSensorEntityDescription(
        key="capacity",
        translation_key="park_and_ride_capacity",
        value_fn=lambda p: p.capacite,
    ),
    DataGrandLyonParkAndRideSensorEntityDescription(
        key="accessible_spaces",
        translation_key="accessible_spaces",
        value_fn=lambda p: p.place_handi,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    DataGrandLyonParkAndRideSensorEntityDescription(
        key="opening_hours",
        translation_key="opening_hours",
        value_fn=lambda p: p.horaires,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    DataGrandLyonParkAndRideSensorEntityDescription(
        key="name",
        translation_key="park_and_ride_name",
        value_fn=lambda p: p.nom,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DataGrandLyonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Data Grand Lyon sensor entities."""
    tcl_coordinator = entry.runtime_data.tcl_coordinator
    velov_coordinator = entry.runtime_data.velov_coordinator
    park_and_ride_coordinator = entry.runtime_data.park_and_ride_coordinator

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_STOP):
        async_add_entities(
            (
                DataGrandLyonStopSensor(tcl_coordinator, subentry, description)
                for description in STOP_SENSOR_DESCRIPTIONS
            ),
            config_subentry_id=subentry.subentry_id,
        )

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_VELOV_STATION):
        async_add_entities(
            (
                DataGrandLyonVelovSensor(velov_coordinator, subentry, description)
                for description in VELOV_SENSOR_DESCRIPTIONS
            ),
            config_subentry_id=subentry.subentry_id,
        )

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_PARK_AND_RIDE):
        async_add_entities(
            (
                DataGrandLyonParkAndRideSensor(
                    park_and_ride_coordinator, subentry, description
                )
                for description in PARK_AND_RIDE_SENSOR_DESCRIPTIONS
            ),
            config_subentry_id=subentry.subentry_id,
        )


class DataGrandLyonStopSensor(DataGrandLyonTclEntity, SensorEntity):
    """Sensor for Data Grand Lyon stop departures."""

    entity_description: DataGrandLyonStopSensorEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return True if the departure index exists."""
        return super().available and self.entity_description.departure_index < len(
            self.coordinator.data[self._subentry_id]
        )

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the sensor value."""
        departure = self.coordinator.data[self._subentry_id][
            self.entity_description.departure_index
        ]
        return self.entity_description.value_fn(departure)


class DataGrandLyonVelovSensor(DataGrandLyonVelovEntity, SensorEntity):
    """Sensor for Data Grand Lyon Vélo'v station."""

    entity_description: DataGrandLyonVelovSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self.coordinator.data[self._subentry_id]
        )


class DataGrandLyonParkAndRideSensor(DataGrandLyonParkAndRideEntity, SensorEntity):
    """Sensor for Data Grand Lyon park-and-ride facility."""

    entity_description: DataGrandLyonParkAndRideSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self.coordinator.data[self._subentry_id]
        )
