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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IntellifireDataUpdateCoordinator
from .const import DOMAIN


@dataclass
class IntellifireSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[IntellifirePollData], bool]


@dataclass
class IntellifireBinarySensorEntityDescription(
    BinarySensorEntityDescription, IntellifireSensorEntityDescriptionMixin
):
    """Describes a binary sensor entity."""


INTELLIFIRE_BINARY_SENSORS: tuple[IntellifireBinarySensorEntityDescription, ...] = (
    IntellifireBinarySensorEntityDescription(
        key="on_off",  # This is the sensor name
        name="Power",  # This is the human readable name
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda data: data.is_on,
    ),
    IntellifireBinarySensorEntityDescription(
        key="timer_on",
        name="Timer On",
        icon="mdi:camera-timer",
        value_fn=lambda data: data.timer_on,
    ),
    IntellifireBinarySensorEntityDescription(
        key="pilot_light_on",
        name="Pilot Light On",
        icon="mdi:fire-alert",
        value_fn=lambda data: data.pilot_on,
    ),
    IntellifireBinarySensorEntityDescription(
        key="thermostat_on",
        name="Thermostat On",
        icon="mdi:home-thermometer-outline",
        value_fn=lambda data: data.thermostat_on,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a IntelliFire On/Off Sensor."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        IntellifireBinarySensor(
            coordinator=coordinator, entry_id=entry.entry_id, description=description
        )
        for description in INTELLIFIRE_BINARY_SENSORS
    )


class IntellifireBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """A semi-generic wrapper around Binary Sensor entities for IntelliFire."""

    # Define types
    coordinator: IntellifireDataUpdateCoordinator
    entity_description: IntellifireBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: IntellifireDataUpdateCoordinator,
        entry_id,
        description: IntellifireBinarySensorEntityDescription,
    ):
        """Class initializer."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description

        # Set the Display name the User will see
        self._attr_name = f"Fireplace {description.name}"
        self._attr_unique_id = (
            f"IntelliFire_{description.key}_{coordinator.api.data.serial}"
        )
        # Configure the Device Info
        self._attr_device_info = self.coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Use this to get the correct value."""
        return self.entity_description.value_fn(self.coordinator.api.data)
