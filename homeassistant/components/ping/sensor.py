"""Sensor platform that for Ping integration."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PingConfigEntry
from .coordinator import PingResult, PingUpdateCoordinator
from .entity import PingEntity


@dataclass(frozen=True, kw_only=True)
class PingSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Ping sensor entity."""

    value_fn: Callable[[PingResult], float | None]
    has_fn: Callable[[PingResult], bool]


SENSORS: tuple[PingSensorEntityDescription, ...] = (
    PingSensorEntityDescription(
        key="round_trip_time_avg",
        translation_key="round_trip_time_avg",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda result: result.data.get("avg"),
        has_fn=lambda result: "avg" in result.data,
    ),
    PingSensorEntityDescription(
        key="round_trip_time_max",
        translation_key="round_trip_time_max",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda result: result.data.get("max"),
        has_fn=lambda result: "max" in result.data,
    ),
    PingSensorEntityDescription(
        key="round_trip_time_mdev",
        translation_key="round_trip_time_mdev",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda result: result.data.get("mdev"),
        has_fn=lambda result: "mdev" in result.data,
    ),
    PingSensorEntityDescription(
        key="round_trip_time_min",
        translation_key="round_trip_time_min",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda result: result.data.get("min"),
        has_fn=lambda result: "min" in result.data,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PingConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ping sensors from config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        PingSensor(entry, description, coordinator)
        for description in SENSORS
        if description.has_fn(coordinator.data)
    )


class PingSensor(PingEntity, SensorEntity):
    """Represents a Ping sensor."""

    entity_description: PingSensorEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        description: PingSensorEntityDescription,
        coordinator: PingUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            config_entry, coordinator, f"{config_entry.entry_id}-{description.key}"
        )

        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data.is_alive

    @property
    def native_value(self) -> float | None:
        """Return the sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)
