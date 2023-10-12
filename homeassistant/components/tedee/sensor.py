"""Tedee sensor entities."""
from collections.abc import Callable
from dataclasses import dataclass
import logging

from pytedee_async import Lock as TedeeLock

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from .const import DOMAIN
from .entity import TedeeEntity, TedeeEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass
class TedeeSensorEntityDescriptionMixin:
    """Mixin functions for Tedee sensor entity description."""

    value_fn: Callable[[TedeeLock], int]


@dataclass
class TedeeSensorEntityDescription(
    SensorEntityDescription, TedeeEntityDescription, TedeeSensorEntityDescriptionMixin
):
    """Describes Tedee sensor entity."""


ENTITIES: tuple[TedeeSensorEntityDescription, ...] = (
    TedeeSensorEntityDescription(
        key="battery_sensor",
        translation_key="battery_sensor",
        unique_id_fn=lambda lock: f"{lock.id}-battery-sensor",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda lock: lock.battery_level,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Tedee sensor entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    for entity_description in ENTITIES:
        async_add_entities(
            [
                TedeeSensorEntity(lock, coordinator, entity_description)
                for lock in coordinator.data.values()
            ]
        )


class TedeeSensorEntity(TedeeEntity, SensorEntity):
    """Tedee sensor entity."""

    entity_description: TedeeSensorEntityDescription

    def __init__(self, lock, coordinator, entity_description):
        """Initialize Tedee sensor entity."""
        _LOGGER.debug("Setting up SensorEntity for %s", lock.name)
        super().__init__(lock, coordinator, entity_description)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._lock)
