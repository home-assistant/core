"""Support for Daikin AC sensors."""
import logging

from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE
from homeassistant.helpers.entity import Entity
from homeassistant.util.unit_system import UnitSystem

from . import DOMAIN as DAIKIN_DOMAIN
from .const import (
    ATTR_INSIDE_TEMPERATURE,
    ATTR_OUTSIDE_TEMPERATURE,
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
    async_add_entities(
        [
            DaikinClimateSensor(daikin_api, sensor, hass.config.units)
            for sensor in sensors
        ]
    )


class DaikinClimateSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, api, monitored_state, units: UnitSystem, name=None) -> None:
        """Initialize the sensor."""
        self._api = api
        self._sensor = SENSOR_TYPES.get(monitored_state)
        if name is None:
            name = f"{self._sensor[CONF_NAME]} {api.name}"

        self._name = f"{name} {monitored_state.replace('_', ' ')}"
        self._device_attribute = monitored_state

        if self._sensor[CONF_TYPE] == SENSOR_TYPE_TEMPERATURE:
            self._unit_of_measurement = units.temperature_unit

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._api.mac}-{self._device_attribute}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._sensor[CONF_ICON]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._device_attribute == ATTR_INSIDE_TEMPERATURE:
            return self._api.device.inside_temperature
        if self._device_attribute == ATTR_OUTSIDE_TEMPERATURE:
            return self._api.device.outside_temperature
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    async def async_update(self):
        """Retrieve latest state."""
        await self._api.async_update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info
