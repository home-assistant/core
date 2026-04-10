"""Sensor platform for the Data Grand Lyon integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from data_grand_lyon_ha import TclPassage, TclPassageType, VelovStation

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SUBENTRY_TYPE_STOP, SUBENTRY_TYPE_VELOV
from .coordinator import DataGrandLyonConfigEntry, DataGrandLyonCoordinator

PARALLEL_UPDATES = 0

_TZ_PARIS = ZoneInfo("Europe/Paris")


@dataclass(frozen=True, kw_only=True)
class DataGrandLyonStopSensorEntityDescription(SensorEntityDescription):
    """Describes a Data Grand Lyon stop passage sensor entity."""

    passage_index: int


@dataclass(frozen=True, kw_only=True)
class DataGrandLyonVelovSensorEntityDescription(SensorEntityDescription):
    """Describes a Data Grand Lyon Vélo'v sensor entity."""

    value_fn: Callable[[VelovStation], int | None]


STOP_SENSOR_DESCRIPTIONS: tuple[DataGrandLyonStopSensorEntityDescription, ...] = (
    DataGrandLyonStopSensorEntityDescription(
        key="next_passage_1",
        translation_key="next_passage_1",
        device_class=SensorDeviceClass.TIMESTAMP,
        passage_index=0,
    ),
    DataGrandLyonStopSensorEntityDescription(
        key="next_passage_2",
        translation_key="next_passage_2",
        device_class=SensorDeviceClass.TIMESTAMP,
        passage_index=1,
    ),
    DataGrandLyonStopSensorEntityDescription(
        key="next_passage_3",
        translation_key="next_passage_3",
        device_class=SensorDeviceClass.TIMESTAMP,
        passage_index=2,
    ),
)

VELOV_SENSOR_DESCRIPTIONS: tuple[DataGrandLyonVelovSensorEntityDescription, ...] = (
    DataGrandLyonVelovSensorEntityDescription(
        key="available_bikes",
        translation_key="available_bikes",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.available_bikes,
    ),
    DataGrandLyonVelovSensorEntityDescription(
        key="available_electrical_bikes",
        translation_key="available_electrical_bikes",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.total_stands.electrical_bikes,
    ),
    DataGrandLyonVelovSensorEntityDescription(
        key="available_mechanical_bikes",
        translation_key="available_mechanical_bikes",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.total_stands.mechanical_bikes,
    ),
    DataGrandLyonVelovSensorEntityDescription(
        key="available_bike_stands",
        translation_key="available_bike_stands",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.available_bike_stands,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DataGrandLyonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Data Grand Lyon sensor entities."""
    coordinator = entry.runtime_data

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type == SUBENTRY_TYPE_STOP:
            async_add_entities(
                (
                    DataGrandLyonStopSensor(coordinator, subentry, description)
                    for description in STOP_SENSOR_DESCRIPTIONS
                ),
                config_subentry_id=subentry_id,
            )
        elif subentry.subentry_type == SUBENTRY_TYPE_VELOV:
            async_add_entities(
                (
                    DataGrandLyonVelovSensor(coordinator, subentry, description)
                    for description in VELOV_SENSOR_DESCRIPTIONS
                ),
                config_subentry_id=subentry_id,
            )


class DataGrandLyonStopSensor(
    CoordinatorEntity[DataGrandLyonCoordinator], SensorEntity
):
    """Sensor for Data Grand Lyon stop passages."""

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

        self._attr_unique_id = f"{self._subentry_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._subentry_id)},
            name=subentry.title,
            manufacturer="TCL",
            model="Stop",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _get_passage(self) -> TclPassage | None:
        """Return the passage for this sensor's index, or None."""
        passages = self.coordinator.data.stops.get(self._subentry_id, [])
        index = self.entity_description.passage_index
        if index >= len(passages):
            return None
        return passages[index]

    @property
    def native_value(self) -> datetime | None:
        """Return the passage time."""
        passage = self._get_passage()
        if passage is None:
            return None
        dt = passage.heure_passage
        if dt.tzinfo is None:
            return dt.replace(tzinfo=_TZ_PARIS)
        return dt

    @property
    def icon(self) -> str:
        """Return icon based on passage type."""
        passage = self._get_passage()
        if passage is not None and passage.type == TclPassageType.ESTIMATED:
            return "mdi:clock-check-outline"
        return "mdi:clock-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return line and direction as extra attributes."""
        passage = self._get_passage()
        if passage is None:
            return None
        return {
            "line": passage.ligne,
            "direction": passage.direction,
            "type": passage.type.name.lower(),
        }


class DataGrandLyonVelovSensor(
    CoordinatorEntity[DataGrandLyonCoordinator], SensorEntity
):
    """Sensor for Vélo'v station data."""

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

        self._attr_unique_id = f"{self._subentry_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._subentry_id)},
            name=subentry.title,
            manufacturer="JCDecaux",
            model="Vélo'v",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        station = self.coordinator.data.velov.get(self._subentry_id)
        if station is None:
            return None
        return self.entity_description.value_fn(station)
