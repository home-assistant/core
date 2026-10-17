"""Sensor platform that for Ping integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PingConfigEntry, PingResult, PingUpdateCoordinator
from .entity import PingEntity
from .helpers import PingDataICMPLib


@dataclass(frozen=True, kw_only=True)
class PingSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Ping sensor entity."""

    value_fn: Callable[[PingResult], float | None]
    has_fn: Callable[[PingResult], bool]
    supported_fn: Callable[[PingUpdateCoordinator], bool] = lambda _: True


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
        supported_fn=lambda coordinator: "mdev" in coordinator.data.data,
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
    PingSensorEntityDescription(
        key="jitter",
        translation_key="jitter",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda result: result.data.get("jitter"),
        has_fn=lambda result: "jitter" in result.data,
        supported_fn=lambda coordinator: isinstance(coordinator.ping, PingDataICMPLib),
    ),
    PingSensorEntityDescription(
        key="loss",
        translation_key="loss",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda result: result.data.get("loss"),
        has_fn=lambda result: "loss" in result.data,
        supported_fn=lambda coordinator: isinstance(coordinator.ping, PingDataICMPLib),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ping sensors from config entry."""
    coordinator = entry.runtime_data
    known_sensors: set[str] = set()
    remove_listener: Callable[[], None] | None = None

    @callback
    def async_add_sensors() -> None:
        """Add supported sensors that have not been created yet."""
        nonlocal remove_listener
        new_sensors = []
        for description in SENSORS:
            if description.key in known_sensors or not description.supported_fn(
                coordinator
            ):
                continue
            known_sensors.add(description.key)
            new_sensors.append(PingSensor(entry, description, coordinator))
        if new_sensors:
            async_add_entities(new_sensors)
        if remove_listener is not None and coordinator.data.is_alive:
            remove_listener()
            remove_listener = None

    async_add_sensors()
    if (
        not isinstance(coordinator.ping, PingDataICMPLib)
        and not coordinator.data.is_alive
    ):
        # The ping binary's first successful response determines mdev support.
        remove_listener = coordinator.async_add_listener(async_add_sensors)
        entry.async_on_unload(
            lambda: remove_listener() if remove_listener is not None else None
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
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.entity_description.has_fn(
            self.coordinator.data
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)
