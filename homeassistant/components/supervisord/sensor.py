"""Sensor for Supervisord process status."""
import logging
import xmlrpc.client

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_URL
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_DESCRIPTION = 'description'
ATTR_GROUP = 'group'

DEFAULT_URL = 'http://localhost:9001/RPC2'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_URL, default=DEFAULT_URL): cv.url,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Supervisord platform."""
    url = config.get(CONF_URL)
    try:
        supervisor_server = xmlrpc.client.ServerProxy(url)
        processes = supervisor_server.supervisor.getAllProcessInfo()
    except ConnectionRefusedError:
        _LOGGER.error("Could not connect to Supervisord")
        return False

    add_entities(
        [SupervisorProcessSensor(info, supervisor_server)
         for info in processes], True)


class SupervisorProcessSensor(Entity):
    """Representation of a supervisor-monitored process."""

    def __init__(self, info, server):
        """Initialize the sensor."""
        self._info = info
        self._server = server
        self._available = True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._info.get('name')

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._info.get('statename')

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DESCRIPTION: self._info.get('description'),
            ATTR_GROUP: self._info.get('group'),
        }

    def update(self):
        """Update device state."""
        try:
            self._info = self._server.supervisor.getProcessInfo(
                self._info.get('name'))
            self._available = True
        except ConnectionRefusedError:
            _LOGGER.warning("Supervisord not available")
            self._available = False
