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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import TrainData, TVDataUpdateCoordinator


ATTR_PRODUCT_FILTER = "product_filter"


@dataclass
class TrafikverketRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[TrainData], StateType | datetime]


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
    ),
    TrafikverketSensorEntityDescription(
        key="departure_state",
        translation_key="departure_state",
        icon="mdi:clock",
        value_fn=lambda data: data.departure_state,
        device_class=SensorDeviceClass.ENUM,
        options=["on_time", "delayed", "canceled"],
    ),
    TrafikverketSensorEntityDescription(
        key="cancelled",
        translation_key="cancelled",
        icon="mdi:alert",
        value_fn=lambda data: data.cancelled,
    ),
    TrafikverketSensorEntityDescription(
        key="delayed_time",
        translation_key="delayed_time",
        icon="mdi:clock",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.delayed_time,
    ),
    TrafikverketSensorEntityDescription(
        key="planned_time",
        translation_key="planned_time",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.planned_time,
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="estimated_time",
        translation_key="estimated_time",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.estimated_time,
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="actual_time",
        translation_key="actual_time",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.actual_time,
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="other_info",
        translation_key="other_info",
        icon="mdi:information-variant",
        value_fn=lambda data: data.other_info,
    ),
    TrafikverketSensorEntityDescription(
        key="deviation",
        translation_key="deviation",
        icon="mdi:alert",
        value_fn=lambda data: data.deviation,
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
        return {ATTR_PRODUCT_FILTER: self.coordinator.data.product_filter}
