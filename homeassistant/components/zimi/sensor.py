"""Platform for sensor integration."""

from __future__ import annotations

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

from . import ZimiConfigEntry
from .entity import ZimiEntity

SENSOR_KEY_DOOR_TEMP = "door_temperature"
SENSOR_KEY_GARAGE_BATTERY = "garage_battery"
SENSOR_KEY_GARAGE_HUMDITY = "garage_humidty"
SENSOR_KEY_GARAGE_TEMP = "garage_temperature"

GARAGE_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=SENSOR_KEY_DOOR_TEMP,
        name="Outside temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key=SENSOR_KEY_GARAGE_BATTERY,
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.BATTERY,
    ),
    SensorEntityDescription(
        key=SENSOR_KEY_GARAGE_TEMP,
        name="Garage temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key=SENSOR_KEY_GARAGE_HUMDITY,
        name="Garage humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
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

    async_add_entities(ZimiSensor(device, description, api) for device in api.sensors for description in GARAGE_SENSOR_DESCRIPTIONS)


class ZimiSensor(ZimiEntity, SensorEntity):
    """Representation of a Zimi sensor."""

    def __init__(
        self,
        device: ControlPointDevice,
        description: SensorEntityDescription,
        api: ControlPoint,
    ) -> None:
        """Initialize an ZimiSensor with specified type."""

        super().__init__(device, api)

        self.entity_description = description
        self._attr_unique_id = device.identifier + "." + self.entity_description.key

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""

        if self.entity_description.key == SENSOR_KEY_DOOR_TEMP:
            return self._device.door_temp

        if self.entity_description.key == SENSOR_KEY_GARAGE_BATTERY:
            return self._device.battery_level

        if self.entity_description.key == SENSOR_KEY_GARAGE_HUMDITY:
            return self._device.garage_humidity

        if self.entity_description.key == SENSOR_KEY_GARAGE_TEMP:
            return self._device.garage_temp

        return None
