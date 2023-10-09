import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (SensorDeviceClass, SensorEntity,
                                             SensorEntityDescription,
                                             SensorStateClass)
from pytedee_async import Lock as TedeeLock

from .const import DOMAIN
from .entity import TedeeEntity, TedeeEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass
class TedeeSensorEntityDescriptionMixin:
    """Mixin functions for Tedee sensor entity description."""
    value_fn: Callable[[TedeeLock], int]


@dataclass
class TedeeSensorEntityDescription(
        SensorEntityDescription, 
        TedeeEntityDescription,
        TedeeSensorEntityDescriptionMixin
    ):
    """Describes Tedee sensor entity."""

ENTITIES: tuple[TedeeSensorEntityDescription, ...] = (
    TedeeSensorEntityDescription(
        key="battery_sensor",
        translation_key="battery_sensor",
        unique_id_fn=lambda lock: f"{lock.id}-battery-sensor",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement='%',
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda lock: lock.battery_level,
    ),
)

async def async_setup_entry(hass, entry, async_add_entities):
    
    coordinator = hass.data[DOMAIN][entry.entry_id]

    for entity_description in ENTITIES:
        async_add_entities(
            [TedeeSensorEntity(lock, coordinator, entity_description) for lock in coordinator.data.values()]
        )


class TedeeSensorEntity(TedeeEntity, SensorEntity):

    def __init__(self, lock, coordinator, entity_description):
        _LOGGER.debug("Setting up SensorEntity for %s", lock.name)
        super().__init__(lock, coordinator, entity_description)

    @property
    def native_value(self):
        return self.entity_description.value_fn(self._lock)