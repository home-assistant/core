"""
Support for Velbus platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/velbus/
"""
import asyncio
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, CONF_PORT
from homeassistant.helpers.discovery import async_load_platform

REQUIREMENTS = ['python-velbus==2.0.15']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'velbus'


VELBUS_MESSAGE = 'velbus.message'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Velbus platform."""
    import velbus
    port = config[DOMAIN].get(CONF_PORT)
    controller = velbus.Controller(port)
    hass.data[DOMAIN] = controller

    def stop_velbus(event):
        """Disconnect from serial port."""
        _LOGGER.debug("Shutting down ")
        controller.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_velbus)

    def callback():
        hass.async_add_job(async_load_platform(hass, 'switch', DOMAIN))
        hass.async_add_job(async_load_platform(hass, 'binary_sensor', DOMAIN))

    controller.scan(callback)

    return True
