"""Component for interfacing to Lutron Homeworks Series 4 and 8 systems.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homeworks/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    dispatcher_send)

REQUIREMENTS = ['pyhomeworks==0.0.6']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'homeworks'

HOMEWORKS_CONTROLLER = 'homeworks'
ENTITY_SIGNAL = 'homeworks_entity_{}'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, base_config):
    """Start Homeworks controller."""
    from pyhomeworks.pyhomeworks import Homeworks

    class HomeworksController(Homeworks):
        """Interface between HASS and Homeworks controller."""

        def __init__(self, host, port):
            """Host and port of Lutron Homeworks controller."""
            super().__init__(host, port, self.callback)

        def callback(self, msg_type, values):
            """Dispatch state changes."""
            _LOGGER.debug('callback: %s, %s', msg_type, values)
            addr = values[0]
            signal = ENTITY_SIGNAL.format(addr)
            dispatcher_send(hass, signal, (msg_type, values))
            _LOGGER.debug('callback returned')

    config = base_config.get(DOMAIN)
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    controller = HomeworksController(host, port)
    hass.data[HOMEWORKS_CONTROLLER] = controller

    def cleanup(event):
        controller.close()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)
    return True


class HomeworksDevice():
    """Base class of a Homeworks device."""

    def __init__(self, controller, addr, name):
        """Controller, address, and name of the device."""
        self._addr = addr
        self._name = name
        self._controller = controller

    def addr(self):
        """Device address."""
        return self._addr

    @property
    def name(self):
        """Device name."""
        return self._name

    @property
    def should_poll(self):
        """No need to poll."""
        return False
