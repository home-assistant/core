"""
Support for Daikin AC Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.daikin/
"""
import logging
import voluptuous as vol

from homeassistant.components.daikin import (
    SENSOR_TYPES,
    ATTR_INSIDE_TEMPERATURE, ATTR_OUTSIDE_TEMPERATURE,
    daikin_api_setup
)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_ICON,
    CONF_MONITORED_CONDITIONS, CONF_TEMPERATURE_UNIT
)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=None): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_TYPES.keys()):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Daikin sensors."""
    if discovery_info is not None:
        host = discovery_info.get('ip')
        name = None
        monitored_conditions = discovery_info.get(
            CONF_MONITORED_CONDITIONS, list(SENSOR_TYPES.keys())
        )
    else:
        host = config.get(CONF_HOST)
        name = config.get(CONF_NAME)
        monitored_conditions = config.get(CONF_MONITORED_CONDITIONS)
        _LOGGER.info("Added Daikin AC sensor on %s", host)

    api = daikin_api_setup(hass, host, name)

    sensors = []
    for monitored_state in monitored_conditions:
        sensors.append(DaikinClimateSensor(api, name, monitored_state))

    add_devices(sensors, True)


class DaikinClimateSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, api, name=None, monitored_state=SENSOR_TYPES.keys()):
        """Initialize the sensor."""
        self._api = api
        self._sensor = SENSOR_TYPES.get(monitored_state)
        if name is None:
            name = "{} {}".format(self._sensor[CONF_NAME], api.name)

        self._name = name
        self._device_attribute = monitored_state

    def get(self, key):
        """Retrieve device settings from API library cache."""
        value = None
        cast_to_float = False

        if key == ATTR_INSIDE_TEMPERATURE:
            value = self._api.device.values.get('htemp')
            cast_to_float = True
        elif key == ATTR_OUTSIDE_TEMPERATURE:
            value = self._api.device.values.get('otemp')

        if value is None:
            _LOGGER.warning("Invalid value requested for key %s", key)
        else:
            if value == "-" or value == "--":
                value = None
            elif cast_to_float:
                try:
                    value = float(value)
                except ValueError:
                    value = None

        return value

    @property
    def unique_id(self):
        """Return the ID of this AC."""
        return "{}.{}".format(self.__class__, self._api.ip_address)

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
        return self.get(self._device_attribute)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._sensor[CONF_TEMPERATURE_UNIT]

    def update(self):
        """Retrieve latest state."""
        self._api.update()
