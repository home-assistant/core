"""Contains binary sensors exposed by the Starlink integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from starlink_grpc import AlertDict, ObstructionDict, StatusDict

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import StarlinkUpdateCoordinator
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


@dataclass
class StarlinkBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[tuple[StatusDict, ObstructionDict, AlertDict]], bool | None]


@dataclass
class StarlinkBinarySensorEntityDescription(
    BinarySensorEntityDescription, StarlinkBinarySensorEntityDescriptionMixin
):
    """Describes a Starlink binary sensor entity."""


class StarlinkBinarySensorEntity(StarlinkEntity, BinarySensorEntity):
    """A BinarySensorEntity for Starlink devices. Handles creating unique IDs."""

    entity_description: StarlinkBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: StarlinkUpdateCoordinator,
        description: StarlinkBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.coordinator.data[0]['id']}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Calculate the binary sensor value from the entity description."""
        return self.entity_description.value_fn(self.coordinator.data)


BINARY_SENSORS = [
    StarlinkBinarySensorEntityDescription(
        key="roaming",
        name="Roaming mode",
        value_fn=lambda data: data[2]["alert_roaming"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="currently_obstructed",
        name="Obstructed",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data[0]["currently_obstructed"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="heating",
        name="Heating",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[2]["alert_is_heating"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="power_save_idle",
        name="Idle",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[2]["alert_is_power_save_idle"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="install_pending",
        name="Update pending",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[2]["alert_install_pending"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="mast_near_vertical",
        name="Mast near vertical",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[2]["alert_mast_not_near_vertical"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="motors_stuck",
        name="Motors stuck",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[2]["alert_motors_stuck"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="slow_ethernet",
        name="Ethernet speeds",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[2]["alert_slow_ethernet_speeds"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="thermal_throttle",
        name="Thermal throttle",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[2]["alert_thermal_throttle"],
    ),
    StarlinkBinarySensorEntityDescription(
        key="unexpected_location",
        name="Unexpected location",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[2]["alert_unexpected_location"],
    ),
]
