"""Diyanet prayer time sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DiyanetConfigEntry
from .coordinator import DiyanetCoordinator


@dataclass(frozen=True, kw_only=True)
class DiyanetSensorEntityDescription(SensorEntityDescription):
    """Describes Diyanet sensor entity."""

    value_fn: Callable[[dict], str | None]


SENSOR_TYPES: tuple[DiyanetSensorEntityDescription, ...] = (
    DiyanetSensorEntityDescription(
        key="fajr",
        translation_key="fajr",
        icon="mdi:weather-sunset-up",
        value_fn=lambda data: data.get("fajr"),
    ),
    DiyanetSensorEntityDescription(
        key="sunrise",
        translation_key="sunrise",
        icon="mdi:weather-sunset-up",
        value_fn=lambda data: data.get("sunrise"),
    ),
    DiyanetSensorEntityDescription(
        key="dhuhr",
        translation_key="dhuhr",
        icon="mdi:weather-sunny",
        value_fn=lambda data: data.get("dhuhr"),
    ),
    DiyanetSensorEntityDescription(
        key="asr",
        translation_key="asr",
        icon="mdi:weather-sunset-down",
        value_fn=lambda data: data.get("asr"),
    ),
    DiyanetSensorEntityDescription(
        key="maghrib",
        translation_key="maghrib",
        icon="mdi:weather-sunset",
        value_fn=lambda data: data.get("maghrib"),
    ),
    DiyanetSensorEntityDescription(
        key="isha",
        translation_key="isha",
        icon="mdi:weather-night",
        value_fn=lambda data: data.get("isha"),
    ),
    DiyanetSensorEntityDescription(
        key="qibla_time",
        translation_key="qibla_time",
        icon="mdi:compass",
        value_fn=lambda data: data.get("qiblaTime"),
    ),
    DiyanetSensorEntityDescription(
        key="hijri_date",
        translation_key="hijri_date",
        icon="mdi:calendar",
        value_fn=lambda data: data.get("hijriDateLong"),
    ),
    DiyanetSensorEntityDescription(
        key="gregorian_date",
        translation_key="gregorian_date",
        icon="mdi:calendar",
        value_fn=lambda data: data.get("gregorianDateLong"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DiyanetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Diyanet sensors from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        DiyanetSensor(coordinator, description) for description in SENSOR_TYPES
    )


class DiyanetSensor(CoordinatorEntity[DiyanetCoordinator], SensorEntity):
    """Representation of a Diyanet sensor."""

    _attr_has_entity_name = True
    entity_description: DiyanetSensorEntityDescription

    def __init__(
        self,
        coordinator: DiyanetCoordinator,
        description: DiyanetSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        # config_entry is guaranteed to be set when passed to coordinator
        assert coordinator.config_entry is not None
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
