"""Train information for departures and delays, provided by Trafikverket."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TVTrainConfigEntry
from .const import ATTRIBUTION, DOMAIN
from .coordinator import TrainData, TVDataUpdateCoordinator

ATTR_PRODUCT_FILTER = "product_filter"

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TrafikverketSensorEntityDescription(SensorEntityDescription):
    """Describes Trafikverket sensor entity."""

    value_fn: Callable[[TrainData], StateType | datetime]


SENSOR_TYPES: tuple[TrafikverketSensorEntityDescription, ...] = (
    TrafikverketSensorEntityDescription(
        key="departure_time",
        translation_key="departure_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.departure_time,
    ),
    TrafikverketSensorEntityDescription(
        key="departure_state",
        translation_key="departure_state",
        value_fn=lambda data: data.departure_state,
        device_class=SensorDeviceClass.ENUM,
        options=["on_time", "delayed", "canceled"],
    ),
    TrafikverketSensorEntityDescription(
        key="cancelled",
        translation_key="cancelled",
        value_fn=lambda data: data.cancelled,
    ),
    TrafikverketSensorEntityDescription(
        key="delayed_time",
        translation_key="delayed_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.delayed_time,
    ),
    TrafikverketSensorEntityDescription(
        key="planned_time",
        translation_key="planned_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.planned_time,
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="estimated_time",
        translation_key="estimated_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.estimated_time,
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="actual_time",
        translation_key="actual_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.actual_time,
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="other_info",
        translation_key="other_info",
        value_fn=lambda data: data.other_info,
    ),
    TrafikverketSensorEntityDescription(
        key="deviation",
        translation_key="deviation",
        value_fn=lambda data: data.deviation,
    ),
    TrafikverketSensorEntityDescription(
        key="departure_time_next",
        translation_key="departure_time_next",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.departure_time_next,
    ),
    TrafikverketSensorEntityDescription(
        key="departure_time_next_next",
        translation_key="departure_time_next_next",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.departure_time_next_next,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TVTrainConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Trafikverket sensor entry."""

    coordinator = entry.runtime_data

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
        self._update_attr()

    @callback
    def _update_attr(self) -> None:
        """Update _attr."""
        self._attr_native_value = self.entity_description.value_fn(
            self.coordinator.data
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_attr()
        return super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional attributes for Trafikverket Train sensor."""
        if self.coordinator.data.product_filter:
            return {ATTR_PRODUCT_FILTER: self.coordinator.data.product_filter}
        return None
