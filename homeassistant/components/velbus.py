"""
Support for Velbus platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/velbus/
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, CONF_PORT

REQUIREMENTS = ['python-velbus==2.0.11']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'velbus'


VELBUS_MESSAGE = 'velbus.message'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Velbus platform."""
    import velbus
    port = config[DOMAIN].get(CONF_PORT)
    connection = velbus.VelbusUSBConnection(port)
    controller = velbus.Controller(connection)
    hass.data[DOMAIN] = controller

    def stop_velbus(event):
        """Disconnect from serial port."""
        _LOGGER.debug("Shutting down ")
        connection.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_velbus)
    return True
