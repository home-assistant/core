"""Support for Ecoforest sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyecoforest.models.device import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EcoforestCoordinator
from .entity import EcoforestEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class EcoforestRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Device], float | None]


@dataclass
class EcoforestSensorEntityDescription(
    SensorEntityDescription, EcoforestRequiredKeysMixin
):
    """Describes Ecoforest sensor entity."""


SENSOR_TYPES: tuple[EcoforestSensorEntityDescription, ...] = (
    EcoforestSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda data: data.environment_temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Ecoforest sensor platform."""
    coordinator: EcoforestCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        EcoforestSensor(coordinator, description) for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class EcoforestSensor(SensorEntity, EcoforestEntity):
    """Representation of an Ecoforest sensor."""

    entity_description: EcoforestSensorEntityDescription

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.data)
