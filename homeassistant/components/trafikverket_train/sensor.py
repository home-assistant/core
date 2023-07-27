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
from homeassistant.const import CONF_NAME, CONF_WEEKDAY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_TIME, DOMAIN
from .coordinator import TrainData, TVDataUpdateCoordinator

ATTR_DEPARTURE_STATE = "departure_state"
ATTR_CANCELLED = "cancelled"
ATTR_DELAY_TIME = "number_of_minutes_delayed"
ATTR_PLANNED_TIME = "planned_time"
ATTR_ESTIMATED_TIME = "estimated_time"
ATTR_ACTUAL_TIME = "actual_time"
ATTR_OTHER_INFORMATION = "other_information"
ATTR_DEVIATIONS = "deviations"

ICON = "mdi:train"
SCAN_INTERVAL = timedelta(minutes=5)


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
            ATTR_CANCELLED: data.cancelled,
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

    to_station = coordinator.to_station
    from_station = coordinator.from_station
    get_time: str | None = entry.data.get(CONF_TIME)
    train_time = dt_util.parse_time(get_time) if get_time else None

    async_add_entities(
        [
            TrainSensor(
                coordinator,
                entry.data[CONF_NAME],
                from_station,
                to_station,
                entry.data[CONF_WEEKDAY],
                train_time,
                entry.entry_id,
                description,
            )
            for description in SENSOR_TYPES
        ],
        True,
    )


class TrainSensor(CoordinatorEntity[TVDataUpdateCoordinator], SensorEntity):
    """Contains data about a train depature."""

    _attr_has_entity_name = True
    entity_description: TrafikverketSensorEntityDescription

    def __init__(
        self,
        coordinator: TVDataUpdateCoordinator,
        name: str,
        from_station: StationInfo,
        to_station: StationInfo,
        weekday: list,
        departuretime: time | None,
        entry_id: str,
        entity_description: TrafikverketSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Trafikverket",
            model="v2.0",
            name=name,
            configuration_url="https://api.trafikinfo.trafikverket.se/",
        )
        self._attr_unique_id = f"{entry_id}-{entity_description.key}"
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
