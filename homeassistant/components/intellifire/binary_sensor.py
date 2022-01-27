"""Support for IntelliFire Binary Sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from intellifire4py import IntellifirePollData

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IntellifireDataUpdateCoordinator
from .const import DOMAIN
from .entity import IntellifireEntity, IntellifireEntityDescription


@dataclass
class IntellifireBinarySensorRequiredKeysMixin:
    """Mixin for required keys."""
    value_fn: Callable[[IntellifirePollData], bool]


@dataclass
class IntellifireBinarySensorEntityDescription(IntellifireEntityDescription,
                                               IntellifireBinarySensorRequiredKeysMixin):
    """Describes a binary sensor entity."""

INTELLIFIRE_BINARY_SENSORS: tuple[IntellifireBinarySensorEntityDescription, ...] = (
    IntellifireBinarySensorEntityDescription(
        key="on_off",  # This is the sensor name
        name="Flame",  # This is the human readable name
        icon="mdi:fire",
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
    def __init__(
            self,
            coordinator: IntellifireDataUpdateCoordinator,
            description: IntellifireBinarySensorEntityDescription,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator, description=description)

        # I was having issues getting value_fn to come across when I was using
        # self.entity_description in the `is_on` function. By setting this value
        # directly -> I was able to access the value_fn call. I'm sure there is
        # a better way to do this - but I'm unsure as how to do it.
        self.description = description

    @property
    def is_on(self) -> bool:

        """Use this to get the correct value."""
        return self.description.value_fn(self.coordinator.api.data)

