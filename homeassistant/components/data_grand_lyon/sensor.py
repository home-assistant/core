"""Sensor platform for the Data Grand Lyon integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from data_grand_lyon_ha import TclPassage, TclPassageType

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

from .const import DOMAIN, SUBENTRY_TYPE_STOP
from .coordinator import DataGrandLyonConfigEntry, DataGrandLyonCoordinator

PARALLEL_UPDATES = 0

_TZ_PARIS = ZoneInfo("Europe/Paris")

_DEPARTURE_TYPE_OPTIONS = [t.name.lower() for t in TclPassageType]


def _departure_time(departure: TclPassage) -> datetime:
    """Return the departure time, localized to Europe/Paris if naive."""
    dt = departure.heure_passage
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_TZ_PARIS)
    return dt


def _departure_icon(departure: TclPassage) -> str:
    """Return icon based on departure type."""
    if departure.type == TclPassageType.ESTIMATED:
        return "mdi:clock-check-outline"
    return "mdi:clock-outline"


@dataclass(frozen=True, kw_only=True)
class DataGrandLyonStopSensorEntityDescription(SensorEntityDescription):
    """Describes a Data Grand Lyon stop departure sensor entity."""

    departure_index: int
    value_fn: Callable[[TclPassage], StateType | datetime]
    icon_fn: Callable[[TclPassage], str] | None = None


STOP_SENSOR_DESCRIPTIONS: tuple[DataGrandLyonStopSensorEntityDescription, ...] = (
    DataGrandLyonStopSensorEntityDescription(
        key="next_departure_1",
        translation_key="next_departure_1",
        device_class=SensorDeviceClass.TIMESTAMP,
        departure_index=0,
        value_fn=_departure_time,
        icon_fn=_departure_icon,
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
        icon_fn=_departure_icon,
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
        icon_fn=_departure_icon,
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
        departures = self.coordinator.data.get(self._subentry_id, [])
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

    @property
    def icon(self) -> str | None:
        """Return a dynamic icon when the description provides one."""
        if self.entity_description.icon_fn is None:
            return None
        departure = self._get_departure()
        if departure is None:
            return None
        return self.entity_description.icon_fn(departure)
