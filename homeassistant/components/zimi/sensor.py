"""Platform for sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from zcc import ControlPoint
from zcc.device import ControlPointDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import ZimiConfigEntry
from .entity import ZimiEntity


@dataclass(frozen=True, kw_only=True)
class ZimiSensorEntityDescription(SensorEntityDescription):
    """Class describing Zimi sensor entities."""

    sensor_name: str | None = None
    value_fn: Callable[[ControlPointDevice], StateType]


GARAGE_SENSOR_DESCRIPTIONS: tuple[ZimiSensorEntityDescription, ...] = (
    ZimiSensorEntityDescription(
        key="door_temperature",
        translation_key="door_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        sensor_name="Outside Temperature",
        value_fn=lambda device: device.door_temp,
    ),
    ZimiSensorEntityDescription(
        key="garage_battery",
        translation_key="garage_battery",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.BATTERY,
        sensor_name="Battery Level",
        value_fn=lambda device: device.battery_level,
    ),
    ZimiSensorEntityDescription(
        key="garage_temperature",
        translation_key="garage_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        sensor_name="Garage Temperature",
        value_fn=lambda device: device.garage_temp,
    ),
    ZimiSensorEntityDescription(
        key="garage_humidty",
        translation_key="garage_humidty",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        sensor_name="Garage Humidity",
        value_fn=lambda device: device.garage_humidity,
    ),
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZimiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zimi Sensor platform."""

    api = config_entry.runtime_data

    async_add_entities(
        ZimiSensor(device, description, api)
        for device in api.sensors
        for description in GARAGE_SENSOR_DESCRIPTIONS
    )


class ZimiSensor(ZimiEntity, SensorEntity):
    """Representation of a Zimi sensor."""

    entity_description: ZimiSensorEntityDescription

    def __init__(
        self,
        device: ControlPointDevice,
        description: ZimiSensorEntityDescription,
        api: ControlPoint,
    ) -> None:
        """Initialize an ZimiSensor with specified type."""

        super().__init__(device, api)

        self.entity_description = description
        self._attr_unique_id = device.identifier + "." + self.entity_description.key
        self._attr_name = self.entity_description.sensor_name

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""

        return self.entity_description.value_fn(self._device)
