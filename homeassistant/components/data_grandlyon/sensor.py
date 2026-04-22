"""Sensor platform for the Data Grand Lyon integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SUBENTRY_TYPE_STOP
from .coordinator import DataGrandLyonConfigEntry, DataGrandLyonCoordinator

PARALLEL_UPDATES = 0

_TZ_PARIS = ZoneInfo("Europe/Paris")


@dataclass(frozen=True, kw_only=True)
class DataGrandLyonStopSensorEntityDescription(SensorEntityDescription):
    """Describes a Data Grand Lyon stop passage sensor entity."""

    passage_index: int


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
        passages = self.coordinator.data.get(self._subentry_id, [])
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
