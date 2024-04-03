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
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import JustNimbusCoordinator
from .const import DOMAIN
from .entity import JustNimbusEntity


@dataclass(frozen=True, kw_only=True)
class JustNimbusEntityDescription(SensorEntityDescription):
    """Describes JustNimbus sensor entity."""

    value_fn: Callable[[JustNimbusCoordinator], Any]


SENSOR_TYPES = (
    JustNimbusEntityDescription(
        key="pump_pressure",
        translation_key="pump_pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.pump_pressure,
    ),
    JustNimbusEntityDescription(
        key="reservoir_temp",
        translation_key="reservoir_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.reservoir_temp,
    ),
    JustNimbusEntityDescription(
        key="reservoir_content",
        translation_key="reservoir_content",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.reservoir_content,
    ),
    JustNimbusEntityDescription(
        key="water_saved",
        translation_key="water_saved",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.water_saved,
    ),
    JustNimbusEntityDescription(
        key="water_used",
        translation_key="water_used",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.water_used,
    ),
    JustNimbusEntityDescription(
        key="reservoir_capacity",
        translation_key="reservoir_capacity",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.reservoir_capacity,
    ),
    JustNimbusEntityDescription(
        key="pump_type",
        translation_key="pump_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.pump_type,
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
