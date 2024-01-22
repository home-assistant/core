"""Support for IntelliFire Binary Sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from intellifire4py import IntellifirePollData

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IntellifireDataUpdateCoordinator
from .const import DOMAIN
from .entity import IntellifireEntity


@dataclass(frozen=True)
class IntellifireBinarySensorRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[IntellifirePollData], bool]


@dataclass(frozen=True)
class IntellifireBinarySensorEntityDescription(
    BinarySensorEntityDescription, IntellifireBinarySensorRequiredKeysMixin
):
    """Describes a binary sensor entity."""


INTELLIFIRE_BINARY_SENSORS: tuple[IntellifireBinarySensorEntityDescription, ...] = (
    IntellifireBinarySensorEntityDescription(
        key="on_off",  # This is the sensor name
        translation_key="flame",  # This is the translation key
        icon="mdi:fire",
        value_fn=lambda data: data.is_on,
    ),
    IntellifireBinarySensorEntityDescription(
        key="timer_on",
        translation_key="timer_on",
        icon="mdi:camera-timer",
        value_fn=lambda data: data.timer_on,
    ),
    IntellifireBinarySensorEntityDescription(
        key="pilot_light_on",
        translation_key="pilot_light_on",
        icon="mdi:fire-alert",
        value_fn=lambda data: data.pilot_on,
    ),
    IntellifireBinarySensorEntityDescription(
        key="thermostat_on",
        translation_key="thermostat_on",
        icon="mdi:home-thermometer-outline",
        value_fn=lambda data: data.thermostat_on,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_pilot_flame",
        translation_key="pilot_flame_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.error_pilot_flame,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_flame",
        translation_key="flame_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.error_flame,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_fan_delay",
        translation_key="fan_delay_error",
        icon="mdi:fan-alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.error_fan_delay,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_maintenance",
        translation_key="maintenance_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.error_maintenance,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_disabled",
        translation_key="disabled_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.error_disabled,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_fan",
        translation_key="fan_error",
        icon="mdi:fan-alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.error_fan,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_lights",
        translation_key="lights_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.error_lights,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_accessory",
        translation_key="accessory_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.error_accessory,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_soft_lock_out",
        translation_key="soft_lock_out_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.error_soft_lock_out,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_ecm_offline",
        translation_key="ecm_offline_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.error_ecm_offline,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    IntellifireBinarySensorEntityDescription(
        key="error_offline",
        translation_key="offline_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.error_offline,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
    def is_on(self) -> bool:
        """Use this to get the correct value."""
        return self.entity_description.value_fn(self.coordinator.read_api.data)
