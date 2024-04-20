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
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import EcoforestCoordinator
from .entity import EcoforestEntity

_LOGGER = logging.getLogger(__name__)

STATUS_TYPE = [s.value for s in State]
ALARM_TYPE = [a.value for a in Alarm] + ["none"]


@dataclass(frozen=True, kw_only=True)
class EcoforestSensorEntityDescription(SensorEntityDescription):
    """Describes Ecoforest sensor entity."""

    value_fn: Callable[[Device], StateType]


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
        value_fn=lambda data: data.alarm.value if data.alarm else "none",
    ),
    EcoforestSensorEntityDescription(
        key="depression",
        translation_key="depression",
        native_unit_of_measurement=UnitOfPressure.PA,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.depression,
    ),
    EcoforestSensorEntityDescription(
        key="working_hours",
        translation_key="working_hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.working_hours,
    ),
    EcoforestSensorEntityDescription(
        key="ignitions",
        translation_key="ignitions",
        native_unit_of_measurement="ignitions",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.ignitions,
    ),
    EcoforestSensorEntityDescription(
        key="live_pulse",
        translation_key="live_pulse",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.live_pulse,
    ),
    EcoforestSensorEntityDescription(
        key="pulse_offset",
        translation_key="pulse_offset",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.pulse_offset,
    ),
    EcoforestSensorEntityDescription(
        key="extractor",
        translation_key="extractor",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.extractor,
    ),
    EcoforestSensorEntityDescription(
        key="convecto_air_flow",
        translation_key="convecto_air_flow",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.convecto_air_flow,
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
