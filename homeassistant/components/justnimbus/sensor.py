"""Support for the JustNimbus platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    EntityCategory,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import JustNimbusCoordinator
from .const import DOMAIN, VOLUME_FLOW_RATE_LITERS_PER_MINUTE
from .entity import JustNimbusEntity


@dataclass
class JustNimbusEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[JustNimbusCoordinator], Any]


@dataclass
class JustNimbusEntityDescription(
    SensorEntityDescription, JustNimbusEntityDescriptionMixin
):
    """Describes JustNimbus sensor entity."""


SENSOR_TYPES = (
    JustNimbusEntityDescription(
        key="pump_flow",
        name="Pump flow",
        icon="mdi:pump",
        native_unit_of_measurement=VOLUME_FLOW_RATE_LITERS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.pump_flow,
    ),
    JustNimbusEntityDescription(
        key="drink_flow",
        name="Drink flow",
        icon="mdi:water-pump",
        native_unit_of_measurement=VOLUME_FLOW_RATE_LITERS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.drink_flow,
    ),
    JustNimbusEntityDescription(
        key="pump_pressure",
        name="Pump pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.pump_pressure,
    ),
    JustNimbusEntityDescription(
        key="pump_starts",
        name="Pump starts",
        icon="mdi:restart",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.pump_starts,
    ),
    JustNimbusEntityDescription(
        key="pump_hours",
        name="Pump hours",
        icon="mdi:clock",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.pump_hours,
    ),
    JustNimbusEntityDescription(
        key="reservoir_temp",
        name="Reservoir Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.reservoir_temp,
    ),
    JustNimbusEntityDescription(
        key="reservoir_content",
        name="Reservoir content",
        icon="mdi:car-coolant-level",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.reservoir_content,
    ),
    JustNimbusEntityDescription(
        key="total_saved",
        name="Total saved",
        icon="mdi:water-opacity",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.total_saved,
    ),
    JustNimbusEntityDescription(
        key="total_replenished",
        name="Total replenished",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.total_replenished,
    ),
    JustNimbusEntityDescription(
        key="error_code",
        name="Error code",
        icon="mdi:bug",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.error_code,
    ),
    JustNimbusEntityDescription(
        key="totver",
        name="Total use",
        icon="mdi:chart-donut",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.totver,
    ),
    JustNimbusEntityDescription(
        key="reservoir_content_max",
        name="Max reservoir content",
        icon="mdi:waves",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.reservoir_content_max,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the JustNimbus sensor."""
    coordinator: JustNimbusCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        JustNimbusSensor(
            device_id=entry.data[CONF_CLIENT_ID],
            description=description,
            coordinator=coordinator,
        )
        for description in SENSOR_TYPES
    )


class JustNimbusSensor(JustNimbusEntity, SensorEntity):
    """Implementation of the JustNimbus sensor."""

    def __init__(
        self,
        *,
        device_id: str,
        description: JustNimbusEntityDescription,
        coordinator: JustNimbusCoordinator,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description: JustNimbusEntityDescription = description
        super().__init__(
            device_id=device_id,
            coordinator=coordinator,
        )
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return sensor state."""
        return self.entity_description.value_fn(self.coordinator)
