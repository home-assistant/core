"""
Support for Daikin AC Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.daikin/
"""
import logging
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_ICON,
    CONF_MONITORED_CONDITIONS, CONF_TEMPERATURE_UNIT
)
import homeassistant.helpers.config_validation as cv

from homeassistant.components.daikin import (
    SENSOR_TYPES,
    manual_device_setup
)

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
        _LOGGER.info("Discovered a Daikin AC sensor on %s", host)
    else:
        host = config.get(CONF_HOST)
        name = config.get(CONF_NAME)
        monitored_conditions = config.get(CONF_MONITORED_CONDITIONS)
        _LOGGER.info("Added Daikin AC sensor on %s", host)

    device = manual_device_setup(hass, host, name)

    sensors = []
    for monitored_state in monitored_conditions:
        sensors.append(DaikinClimateSensor(device, name, monitored_state))

    add_devices(sensors, True)


class DaikinClimateSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, device, name=None, monitored_state=SENSOR_TYPES.keys()):
        """Initialize the sensor."""
        self._device = device
        if name is None:
            name = SENSOR_TYPES.get(monitored_state).get(CONF_NAME) \
                + ' ' + device.name

        self._name = name
        self._state = monitored_state

    @property
    def unique_id(self):
        """Return the ID of this AC."""
        return "{}.{}".format(self.__class__, self._device.ip_address)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        sensor = SENSOR_TYPES.get(self._state)
        return sensor[CONF_ICON]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.get(self._state)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES.get(self._state).get(CONF_TEMPERATURE_UNIT)

    def update(self):
        """Retrieve latest state."""
        self._device.update()
