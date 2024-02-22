"""Contains binary sensors exposed by the Starlink integration."""

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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import StarlinkData
from .entity import StarlinkEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up all binary sensors for this entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        StarlinkBinarySensorEntity(coordinator, description)
        for description in BINARY_SENSORS
    )


@dataclass(frozen=True)
class StarlinkBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[StarlinkData], bool | None]


@dataclass(frozen=True)
class StarlinkBinarySensorEntityDescription(
    BinarySensorEntityDescription, StarlinkBinarySensorEntityDescriptionMixin
):
    """Describes a Starlink binary sensor entity."""


class StarlinkBinarySensorEntity(StarlinkEntity, BinarySensorEntity):
    """A BinarySensorEntity for Starlink devices. Handles creating unique IDs."""

    entity_description: StarlinkBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Calculate the binary sensor value from the entity description."""
        return self.entity_description.value_fn(self.coordinator.data)


BINARY_SENSORS = [
    StarlinkBinarySensorEntityDescription(
        key="update",
        device_class=BinarySensorDeviceClass.UPDATE,
        value_fn=lambda data: data.alert["alert_install_pending"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="roaming",
        translation_key="roaming",
        value_fn=lambda data: data.alert["alert_roaming"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="currently_obstructed",
        translation_key="currently_obstructed",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data.status["currently_obstructed"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="heating",
        translation_key="heating",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alert["alert_is_heating"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="power_save_idle",
        translation_key="power_save_idle",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alert["alert_is_power_save_idle"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="mast_near_vertical",
        translation_key="mast_near_vertical",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alert["alert_mast_not_near_vertical"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="motors_stuck",
        translation_key="motors_stuck",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alert["alert_motors_stuck"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="slow_ethernet",
        translation_key="slow_ethernet",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alert["alert_slow_ethernet_speeds"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="thermal_throttle",
        translation_key="thermal_throttle",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alert["alert_thermal_throttle"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="unexpected_location",
        translation_key="unexpected_location",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alert["alert_unexpected_location"],
    ),
]
