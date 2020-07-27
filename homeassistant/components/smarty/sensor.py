"""Support for Salda Smarty XP/XV Ventilation Unit Sensors."""

import datetime as dt
import logging

from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

from . import DOMAIN, SIGNAL_UPDATE_SMARTY

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Smarty Sensor Platform."""
    smarty = hass.data[DOMAIN]["api"]
    name = hass.data[DOMAIN]["name"]

    sensors = [
        SupplyAirTemperatureSensor(name, smarty),
        ExtractAirTemperatureSensor(name, smarty),
        OutdoorAirTemperatureSensor(name, smarty),
        SupplyFanSpeedSensor(name, smarty),
        ExtractFanSpeedSensor(name, smarty),
        FilterDaysLeftSensor(name, smarty),
    ]

    async_add_entities(sensors, True)


class SmartySensor(Entity):
    """Representation of a Smarty Sensor."""

    def __init__(
        self, name: str, device_class: str, smarty, unit_of_measurement: str = ""
    ):
        """Initialize the entity."""
        self._name = name
        self._state = None
        self._sensor_type = device_class
        self._unit_of_measurement = unit_of_measurement
        self._smarty = smarty

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._sensor_type

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    async def async_added_to_hass(self):
        """Call to update."""
        async_dispatcher_connect(self.hass, SIGNAL_UPDATE_SMARTY, self._update_callback)

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)


class SupplyAirTemperatureSensor(SmartySensor):
    """Supply Air Temperature Sensor."""

    def __init__(self, name, smarty):
        """Supply Air Temperature Init."""
        super().__init__(
            name=f"{name} Supply Air Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            unit_of_measurement=TEMP_CELSIUS,
            smarty=smarty,
        )

    def update(self) -> None:
        """Update state."""
        _LOGGER.debug("Updating sensor %s", self._name)
        self._state = self._smarty.supply_air_temperature


class ExtractAirTemperatureSensor(SmartySensor):
    """Extract Air Temperature Sensor."""

    def __init__(self, name, smarty):
        """Supply Air Temperature Init."""
        super().__init__(
            name=f"{name} Extract Air Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            unit_of_measurement=TEMP_CELSIUS,
            smarty=smarty,
        )

    def update(self) -> None:
        """Update state."""
        _LOGGER.debug("Updating sensor %s", self._name)
        self._state = self._smarty.extract_air_temperature


class OutdoorAirTemperatureSensor(SmartySensor):
    """Extract Air Temperature Sensor."""

    def __init__(self, name, smarty):
        """Outdoor Air Temperature Init."""
        super().__init__(
            name=f"{name} Outdoor Air Temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            unit_of_measurement=TEMP_CELSIUS,
            smarty=smarty,
        )

    def update(self) -> None:
        """Update state."""
        _LOGGER.debug("Updating sensor %s", self._name)
        self._state = self._smarty.outdoor_air_temperature


class SupplyFanSpeedSensor(SmartySensor):
    """Supply Fan Speed RPM."""

    def __init__(self, name, smarty):
        """Supply Fan Speed RPM Init."""
        super().__init__(
            name=f"{name} Supply Fan Speed",
            device_class=None,
            unit_of_measurement=None,
            smarty=smarty,
        )

    def update(self) -> None:
        """Update state."""
        _LOGGER.debug("Updating sensor %s", self._name)
        self._state = self._smarty.supply_fan_speed


class ExtractFanSpeedSensor(SmartySensor):
    """Extract Fan Speed RPM."""

    def __init__(self, name, smarty):
        """Extract Fan Speed RPM Init."""
        super().__init__(
            name=f"{name} Extract Fan Speed",
            device_class=None,
            unit_of_measurement=None,
            smarty=smarty,
        )

    def update(self) -> None:
        """Update state."""
        _LOGGER.debug("Updating sensor %s", self._name)
        self._state = self._smarty.extract_fan_speed


class FilterDaysLeftSensor(SmartySensor):
    """Filter Days Left."""

    def __init__(self, name, smarty):
        """Filter Days Left Init."""
        super().__init__(
            name=f"{name} Filter Days Left",
            device_class=DEVICE_CLASS_TIMESTAMP,
            unit_of_measurement=None,
            smarty=smarty,
        )
        self._days_left = 91

    def update(self) -> None:
        """Update state."""
        _LOGGER.debug("Updating sensor %s", self._name)
        days_left = self._smarty.filter_timer
        if days_left is not None and days_left != self._days_left:
            self._state = dt_util.now() + dt.timedelta(days=days_left)
            self._days_left = days_left
