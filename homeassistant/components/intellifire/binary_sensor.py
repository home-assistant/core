"""Support for IntelliFire Binary Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IntellifireDataUpdateCoordinator
from .const import DOMAIN
from .entity import IntellifireEntity


@dataclass(frozen=True)
class IntellifireBinarySensorRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[IntellifireDataUpdateCoordinator], bool | None]


@dataclass(frozen=True)
class IntellifireBinarySensorEntityDescription(
    BinarySensorEntityDescription, IntellifireBinarySensorRequiredKeysMixin
):
    """Describes a binary sensor entity."""


INTELLIFIRE_BINARY_SENSORS: tuple[IntellifireBinarySensorEntityDescription, ...] = (
    IntellifireBinarySensorEntityDescription(
        key="on_off",  # This is the sensor name
        translation_key="flame",  # This is the translation key
        value_fn=lambda coordinator: coordinator.data.is_on,
    ),
    IntellifireBinarySensorEntityDescription(
        key="timer_on",
        translation_key="timer_on",
        value_fn=lambda coordinator: coordinator.data.timer_on,
    ),
    IntellifireBinarySensorEntityDescription(
        key="pilot_light_on",
        translation_key="pilot_light_on",
        value_fn=lambda coordinator: coordinator.data.pilot_on,
    ),
    IntellifireBinarySensorEntityDescription(
        key="thermostat_on",
        translation_key="thermostat_on",
        value_fn=lambda coordinator: coordinator.data.thermostat_on,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_pilot_flame",
        translation_key="pilot_flame_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.error_pilot_flame,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_flame",
        translation_key="flame_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.error_flame,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_fan_delay",
        translation_key="fan_delay_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.error_fan_delay,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_maintenance",
        translation_key="maintenance_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.error_maintenance,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_disabled",
        translation_key="disabled_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.error_disabled,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_fan",
        translation_key="fan_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.error_fan,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_lights",
        translation_key="lights_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.error_lights,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_accessory",
        translation_key="accessory_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.error_accessory,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_soft_lock_out",
        translation_key="soft_lock_out_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.error_soft_lock_out,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_ecm_offline",
        translation_key="ecm_offline_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.error_ecm_offline,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_offline",
        translation_key="offline_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.error_offline,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="local_connectivity",
        translation_key="local_connectivity",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda coordinator: coordinator.fireplace.local_connectivity,
    ),
    IntellifireBinarySensorEntityDescription(
        key="cloud_connectivity",
        translation_key="cloud_connectivity",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda coordinator: coordinator.fireplace.cloud_connectivity,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a IntelliFire On/Off Sensor."""
    coordinator: IntellifireDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        IntellifireBinarySensor(coordinator=coordinator, description=description)
        for description in INTELLIFIRE_BINARY_SENSORS
    )


class IntellifireBinarySensor(IntellifireEntity, BinarySensorEntity):
    """Extends IntellifireEntity with Binary Sensor specific logic."""

    entity_description: IntellifireBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Use this to get the correct value."""
        return self.entity_description.value_fn(self.coordinator)
