"""Support for Daikin AC sensors."""
import logging

from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers.entity import Entity

from . import DOMAIN as DAIKIN_DOMAIN, DaikinApi
from .const import (
    ATTR_COOL_ENERGY,
    ATTR_HEAT_ENERGY,
    ATTR_INSIDE_TEMPERATURE,
    ATTR_OUTSIDE_TEMPERATURE,
    ATTR_TOTAL_POWER,
    SENSOR_TYPE_POWER,
    SENSOR_TYPE_TEMPERATURE,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up the Daikin sensors.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Daikin climate based on config_entry."""
    daikin_api = hass.data[DAIKIN_DOMAIN].get(entry.entry_id)
    sensors = [ATTR_INSIDE_TEMPERATURE]
    if daikin_api.device.support_outside_temperature:
        sensors.append(ATTR_OUTSIDE_TEMPERATURE)
    if daikin_api.device.support_energy_consumption:
        sensors.append(ATTR_TOTAL_POWER)
        sensors.append(ATTR_COOL_ENERGY)
        sensors.append(ATTR_HEAT_ENERGY)
    async_add_entities([DaikinSensor.factory(daikin_api, sensor) for sensor in sensors])


class DaikinSensor(Entity):
    """Representation of a Sensor."""

    @staticmethod
    def factory(api: DaikinApi, monitored_state: str):
        """Initialize any DaikinSensor."""
        cls = {
            SENSOR_TYPE_TEMPERATURE: DaikinClimateSensor,
            SENSOR_TYPE_POWER: DaikinPowerSensor,
        }[SENSOR_TYPES[monitored_state][CONF_TYPE]]
        return cls(api, monitored_state)

    def __init__(self, api: DaikinApi, monitored_state: str) -> None:
        """Initialize the sensor."""
        self._api = api
        self._sensor = SENSOR_TYPES[monitored_state]
        self._name = f"{api.name} {self._sensor[CONF_NAME]}"
        self._device_attribute = monitored_state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._api.device.mac}-{self._device_attribute}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        raise NotImplementedError

    @property
    def device_class(self):
        """Return the class of this device."""
        return self._sensor.get(CONF_DEVICE_CLASS)

    @property
    def icon(self):
        """Return the icon of this device."""
        return self._sensor.get(CONF_ICON)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._sensor[CONF_UNIT_OF_MEASUREMENT]

    async def async_update(self):
        """Retrieve latest state."""
        await self._api.async_update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info


class DaikinClimateSensor(DaikinSensor):
    """Representation of a Climate Sensor."""

    @property
    def state(self):
        """Return the internal state of the sensor."""
        if self._device_attribute == ATTR_INSIDE_TEMPERATURE:
            return self._api.device.inside_temperature
        if self._device_attribute == ATTR_OUTSIDE_TEMPERATURE:
            return self._api.device.outside_temperature
        return None


class DaikinPowerSensor(DaikinSensor):
    """Representation of a power/energy consumption sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._device_attribute == ATTR_TOTAL_POWER:
            return self._api.device.current_total_power_consumption
        if self._device_attribute == ATTR_COOL_ENERGY:
            return self._api.device.last_hour_cool_power_consumption
        if self._device_attribute == ATTR_HEAT_ENERGY:
            return self._api.device.last_hour_heat_power_consumption
        return None
