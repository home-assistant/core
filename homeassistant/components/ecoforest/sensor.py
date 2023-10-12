"""Support for Ecoforest sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyecoforest.models.device import Alarm, Device, State

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import EcoforestCoordinator
from .entity import EcoforestEntity

_LOGGER = logging.getLogger(__name__)

STATUS_TYPE = [s.value for s in State]
ALARM_TYPE = [a.value for a in Alarm] + ["none"]


@dataclass
class EcoforestRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Device], StateType]


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
    EcoforestSensorEntityDescription(
        key="cpu_temperature",
        translation_key="cpu_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.cpu_temperature,
    ),
    EcoforestSensorEntityDescription(
        key="gas_temperature",
        translation_key="gas_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.gas_temperature,
    ),
    EcoforestSensorEntityDescription(
        key="ntc_temperature",
        translation_key="ntc_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.ntc_temperature,
    ),
    EcoforestSensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUS_TYPE,
        value_fn=lambda data: data.state.value,
    ),
    EcoforestSensorEntityDescription(
        key="alarm",
        translation_key="alarm",
        device_class=SensorDeviceClass.ENUM,
        options=ALARM_TYPE,
        icon="mdi:alert",
        value_fn=lambda data: data.alarm.value if data.alarm else "none",
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
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.data)
