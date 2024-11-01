"""Support for the for Danfoss Air HRV sensors."""

from __future__ import annotations

import logging

from pydanfossair.commands import ReadCommand

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, REVOLUTIONS_PER_MINUTE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN as DANFOSS_AIR_DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the available Danfoss Air sensors etc."""
    data = hass.data[DANFOSS_AIR_DOMAIN]

    sensors = [
        [
            "Danfoss Air Exhaust Temperature",
            UnitOfTemperature.CELSIUS,
            ReadCommand.exhaustTemperature,
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
        ],
        [
            "Danfoss Air Outdoor Temperature",
            UnitOfTemperature.CELSIUS,
            ReadCommand.outdoorTemperature,
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
        ],
        [
            "Danfoss Air Supply Temperature",
            UnitOfTemperature.CELSIUS,
            ReadCommand.supplyTemperature,
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
        ],
        [
            "Danfoss Air Extract Temperature",
            UnitOfTemperature.CELSIUS,
            ReadCommand.extractTemperature,
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
        ],
        [
            "Danfoss Air Remaining Filter",
            PERCENTAGE,
            ReadCommand.filterPercent,
            None,
            None,
        ],
        [
            "Danfoss Air Humidity",
            PERCENTAGE,
            ReadCommand.humidity,
            SensorDeviceClass.HUMIDITY,
            SensorStateClass.MEASUREMENT,
        ],
        ["Danfoss Air Fan Step", PERCENTAGE, ReadCommand.fan_step, None, None],
        [
            "Danfoss Air Exhaust Fan Speed",
            REVOLUTIONS_PER_MINUTE,
            ReadCommand.exhaust_fan_speed,
            None,
            None,
        ],
        [
            "Danfoss Air Supply Fan Speed",
            REVOLUTIONS_PER_MINUTE,
            ReadCommand.supply_fan_speed,
            None,
            None,
        ],
        [
            "Danfoss Air Dial Battery",
            PERCENTAGE,
            ReadCommand.battery_percent,
            SensorDeviceClass.BATTERY,
            None,
        ],
    ]

    add_entities(
        (
            DanfossAir(data, sensor[0], sensor[1], sensor[2], sensor[3], sensor[4])
            for sensor in sensors
        ),
        True,
    )


class DanfossAir(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, data, name, sensor_unit, sensor_type, device_class, state_class):
        """Initialize the sensor."""
        self._data = data
        self._attr_name = name
        self._attr_native_value = None
        self._type = sensor_type
        self._attr_native_unit_of_measurement = sensor_unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    def update(self) -> None:
        """Update the new state of the sensor.

        This is done through the DanfossAir object that does the actual
        communication with the Air CCM.
        """
        self._data.update()

        self._attr_native_value = self._data.get_value(self._type)
        if self._attr_native_value is None:
            _LOGGER.debug("Could not get data for %s", self._type)
