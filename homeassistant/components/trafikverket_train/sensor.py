"""Train information for departures and delays, provided by Trafikverket."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from pytrafikverket.trafikverket_train import StationInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_TIME, DOMAIN, ATTRIBUTION
from .coordinator import TrainData, TVDataUpdateCoordinator


@dataclass
class TrafikverketRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[dict[str, StateType | datetime]], StateType | datetime]


@dataclass
class TrafikverketSensorEntityDescription(
    SensorEntityDescription, TrafikverketRequiredKeysMixin
):
    """Describes Trafikverket sensor entity."""


SENSOR_TYPES: tuple[TrafikverketSensorEntityDescription, ...] = (
    TrafikverketSensorEntityDescription(
        key="departure_time",
        name="Departure time",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data["departure_time"],
    ),
    TrafikverketSensorEntityDescription(
        key="departure_state",
        name="Departure state",
        icon="mdi:clock",
        value_fn=lambda data: data["departure_state"],
        device_class="trafikverket_train__depart_state",
    ),
    TrafikverketSensorEntityDescription(
        key="cancelled",
        name="Departure cancelled",
        icon="mdi:alert",
        value_fn=lambda data: data["cancelled"],
    ),
    TrafikverketSensorEntityDescription(
        key="delayed_time",
        name="Delayed time",
        icon="mdi:clock",
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data["delayed_time"],
    ),
    TrafikverketSensorEntityDescription(
        key="planned_time",
        name="Planned time",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data["planned_time"],
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="estimated_time",
        name="Estimated time",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data["estimated_time"],
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="actual_time",
        name="Actual time",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data["actual_time"],
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="other_info",
        name="Other information",
        icon="mdi:information-variant",
        value_fn=lambda data: data["other_info"],
    ),
    TrafikverketSensorEntityDescription(
        key="deviation",
        name="Deviation information",
        icon="mdi:alert",
        value_fn=lambda data: data["deviation"],
    ),
)


@dataclass
class TrafikverketRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[TrainData], StateType | datetime]
    extra_fn: Callable[[TrainData], dict[str, StateType | datetime]]


@dataclass
class TrafikverketSensorEntityDescription(
    SensorEntityDescription, TrafikverketRequiredKeysMixin
):
    """Describes Trafikverket sensor entity."""


SENSOR_TYPES: tuple[TrafikverketSensorEntityDescription, ...] = (
    TrafikverketSensorEntityDescription(
        key="departure_time",
        translation_key="departure_time",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.departure_time,
        extra_fn=lambda data: {
            ATTR_DEPARTURE_STATE: data.departure_state,
            ATTR_CANCELED: data.cancelled,
            ATTR_DELAY_TIME: data.delayed_time,
            ATTR_PLANNED_TIME: data.planned_time,
            ATTR_ESTIMATED_TIME: data.estimated_time,
            ATTR_ACTUAL_TIME: data.actual_time,
            ATTR_OTHER_INFORMATION: data.other_info,
            ATTR_DEVIATIONS: data.deviation,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Trafikverket sensor entry."""

    coordinator: TVDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            TrainSensor(coordinator, entry.data[CONF_NAME], entry.entry_id, description)
            for description in SENSOR_TYPES
        ]
    )


class TrainSensor(CoordinatorEntity[TVDataUpdateCoordinator], SensorEntity):
    """Contains data about a train depature."""

    entity_description: TrafikverketSensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    entity_description: TrafikverketSensorEntityDescription

    def __init__(
        self,
        coordinator: TVDataUpdateCoordinator,
        name: str,
        entry_id: str,
        entity_description: TrafikverketSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}-{entity_description.key}"
        self.entity_description = entity_description
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            name=name,
            configuration_url="https://api.trafikinfo.trafikverket.se/",
        )
        self._attr_extra_state_attributes = {}
        self._update_attr()

    def _update_attr(self) -> None:
        """Update _attr."""
        self._attr_native_value = self.entity_description.value_fn(
            self.coordinator.data
        )
        self._update_attr()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_attr()
        return super()._handle_coordinator_update()

    @callback
    def _update_attr(self) -> None:
        """Retrieve latest states."""
        self._attr_native_value = self.entity_description.value_fn(
            self.coordinator.data
        )
        self._attr_extra_state_attributes = self.entity_description.extra_fn(
            self.coordinator.data
        )
