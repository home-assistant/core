"""
Support for Pilight sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.pilight/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, STATE_UNKNOWN, CONF_UNIT_OF_MEASUREMENT, CONF_PAYLOAD)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.components.pilight as pilight
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_VARIABLE = 'variable'

DEFAULT_NAME = 'Pilight Sensor'
DEPENDENCIES = ['pilight']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_VARIABLE): cv.string,
    vol.Required(CONF_PAYLOAD): vol.Schema(dict),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Pilight Sensor."""
    add_devices([PilightSensor(
        hass=hass,
        name=config.get(CONF_NAME),
        variable=config.get(CONF_VARIABLE),
        payload=config.get(CONF_PAYLOAD),
        unit_of_measurement=config.get(CONF_UNIT_OF_MEASUREMENT)
    )])


class PilightSensor(Entity):
    """Representation of a sensor that can be updated using Pilight."""

    def __init__(self, hass, name, variable, payload, unit_of_measurement):
        """Initialize the sensor."""
        self._state = STATE_UNKNOWN
        self._hass = hass
        self._name = name
        self._variable = variable
        self._payload = payload
        self._unit_of_measurement = unit_of_measurement

        hass.bus.listen(pilight.EVENT, self._handle_code)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    def _handle_code(self, call):
        """Handle received code by the pilight-daemon.

        If the code matches the defined payload
        of this sensor the sensor state is changed accordingly.
        """
        # Check if received code matches defined payload
        # True if payload is contained in received code dict, not
        # all items have to match
        if self._payload.items() <= call.data.items():
            try:
                value = call.data[self._variable]
                self._state = value
                self.schedule_update_ha_state()
            except KeyError:
                _LOGGER.error(
                    'No variable %s in received code data %s',
                    str(self._variable), str(call.data))
