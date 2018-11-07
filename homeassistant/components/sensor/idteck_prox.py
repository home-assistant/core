"""Component for reading from RFK101 proximity card readers.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rfk101/
"""
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_NAME, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['rfk101py==0.0.1']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "IDTECK-Prox"

EVENT_KEYCARD = 'keycard'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the IDTECK proximity card platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)

    try:
        sensor = IDTECKSensor(host, port, name)
    except OSError as error:
        _LOGGER.error("Could not connect to reader. %s", error)
        return False

    def cleanup(event):
        sensor.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)
    add_entities([sensor], True)
    return True


class IDTECKSensor(Entity):
    """Representation of an RFK101 sensor."""

    def __init__(self, host, port, name):
        """Initialize the sensor."""
        self._host = host
        self._port = port
        self._name = name
        self._state = None
        self._connection = None

        from rfk101py.rfk101py import rfk101py
        self._connection = rfk101py(self._host, self._port, self._callback)

    def _callback(self, card):
        """Send a keycard event message into HASS."""
        self.hass.bus.fire(
            EVENT_KEYCARD, {'card': card, 'entity_id': self.entity_id})

    def stop(self):
        """Close resources."""
        if self._connection:
            self._connection.close()
            self._connection = None

    @property
    def device_state_attributes(self):
        """Return supported attributes."""
        return {"Host": self._host, "Port": self._port}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
