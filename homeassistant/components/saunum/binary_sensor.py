"""Binary sensor platform for Saunum Leil Sauna Control Unit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LeilSaunaConfigEntry, LeilSaunaCoordinator
from .entity import LeilSaunaEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LeilSaunaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Saunum Leil binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSORS: tuple[LeilSaunaBinarySensorEntityDescription, ...] = (
    LeilSaunaBinarySensorEntityDescription(
        key="door_status",
        translation_key="door_status",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: bool(data.get("door_status")),
    ),
    LeilSaunaBinarySensorEntityDescription(
        key="alarm_door_open",
        translation_key="alarm_door_open",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data.get("alarm_door_open")),
    ),
    LeilSaunaBinarySensorEntityDescription(
        key="alarm_door_sensor",
        translation_key="alarm_door_sensor",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data.get("alarm_door_sensor")),
    ),
    LeilSaunaBinarySensorEntityDescription(
        key="alarm_thermal_cutoff",
        translation_key="alarm_thermal_cutoff",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data.get("alarm_thermal_cutoff")),
    ),
    LeilSaunaBinarySensorEntityDescription(
        key="alarm_internal_temp",
        translation_key="alarm_internal_temp",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data.get("alarm_internal_temp")),
    ),
    LeilSaunaBinarySensorEntityDescription(
        key="alarm_temp_sensor_shorted",
        translation_key="alarm_temp_sensor_shorted",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data.get("alarm_temp_sensor_shorted")),
    ),
    LeilSaunaBinarySensorEntityDescription(
        key="alarm_temp_sensor_not_connected",
        translation_key="alarm_temp_sensor_not_connected",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data.get("alarm_temp_sensor_not_connected")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeilSaunaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Saunum Leil binary sensor entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        LeilSaunaBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class LeilSaunaBinarySensor(LeilSaunaEntity, BinarySensorEntity):
    """Representation of a Saunum Leil binary sensor."""

    entity_description: LeilSaunaBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: LeilSaunaCoordinator,
        description: LeilSaunaBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)
