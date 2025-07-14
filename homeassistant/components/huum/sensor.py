"""Sensor for max heating time."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HuumDataUpdateCoordinator


@dataclass(kw_only=True, frozen=True)
class HuumSensorEntityDescription(SensorEntityDescription):
    """Class describing Huum sensor entities."""

    value_fn: Callable[[HuumDataUpdateCoordinator], Any]


SENSORS = (
    HuumSensorEntityDescription(
        key="max_heating_time",
        name="Maximum heating time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="h",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.sauna_config.max_heating_time,
    ),
    HuumSensorEntityDescription(
        key="current_heating_end",
        name="Current heating end",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.convert_timestamp(
            coordinator.data.end_date
        )
        if getattr(coordinator.data, "start_date", 0)
        != getattr(coordinator.data, "end_date", 0)
        else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""

    entities = [
        HuumSensor(
            coordinator=hass.data[DOMAIN][entry.entry_id],
            description=sensor_description,
        )
        for sensor_description in SENSORS
    ]

    async_add_entities(entities, True)


class HuumSensor(CoordinatorEntity[HuumDataUpdateCoordinator], SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HuumDataUpdateCoordinator,
        description: HuumSensorEntityDescription,
    ) -> None:
        """Initialize the Sensor."""
        CoordinatorEntity.__init__(self, coordinator)

        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

        self._coordinator: HuumDataUpdateCoordinator = coordinator
        self.entity_description: HuumSensorEntityDescription = description

    @property
    def native_value(self) -> int | None:
        """Return the current value."""
        return self.entity_description.value_fn(self._coordinator)
