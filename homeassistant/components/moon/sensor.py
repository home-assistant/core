"""Support for moon sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import DEGREE, PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MoonConfigEntry
from .const import DEFAULT_NAME, DOMAIN, PHASE_OPTIONS
from .coordinator import MoonData, MoonUpdateCoordinator


@dataclass(kw_only=True, frozen=True)
class MoonSensorEntityDescription(SensorEntityDescription):
    """Description for a moon sensor entity."""

    value_fn: Callable[[MoonData], StateType | datetime | None]


SENSOR_TYPES: tuple[MoonSensorEntityDescription, ...] = (
    MoonSensorEntityDescription(
        key="phase",
        device_class=SensorDeviceClass.ENUM,
        options=PHASE_OPTIONS,
        translation_key="phase",
        value_fn=lambda data: data.phase,
    ),
    MoonSensorEntityDescription(
        key="illumination",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="illumination",
        value_fn=lambda data: data.illumination,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MoonSensorEntityDescription(
        key="next_rising",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_rising",
        value_fn=lambda data: data.next_rising,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MoonSensorEntityDescription(
        key="next_setting",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_setting",
        value_fn=lambda data: data.next_setting,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MoonSensorEntityDescription(
        key="next_new_moon",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_new_moon",
        value_fn=lambda data: data.next_new_moon,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MoonSensorEntityDescription(
        key="next_first_quarter_moon",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_first_quarter_moon",
        value_fn=lambda data: data.next_first_quarter_moon,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MoonSensorEntityDescription(
        key="next_full_moon",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_full_moon",
        value_fn=lambda data: data.next_full_moon,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MoonSensorEntityDescription(
        key="next_last_quarter_moon",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_last_quarter_moon",
        value_fn=lambda data: data.next_last_quarter_moon,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MoonSensorEntityDescription(
        key="next_transit",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_transit",
        value_fn=lambda data: data.next_transit,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MoonSensorEntityDescription(
        key="elevation",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        translation_key="elevation",
        value_fn=lambda data: data.elevation,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    MoonSensorEntityDescription(
        key="azimuth",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        translation_key="azimuth",
        value_fn=lambda data: data.azimuth,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MoonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""
    async_add_entities(
        MoonSensorEntity(entry, entry.runtime_data, description)
        for description in SENSOR_TYPES
    )


class MoonSensorEntity(CoordinatorEntity[MoonUpdateCoordinator], SensorEntity):
    """Representation of a Moon sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: MoonSensorEntityDescription

    def __init__(
        self,
        entry: MoonConfigEntry,
        coordinator: MoonUpdateCoordinator,
        description: MoonSensorEntityDescription,
    ) -> None:
        """Initialize the moon sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_suggested_object_id = f"moon_{description.key}"
        self._attr_unique_id = (
            entry.entry_id
            if description.key == "phase"
            else f"{entry.entry_id}-{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            name=DEFAULT_NAME,
            identifiers={(DOMAIN, entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
