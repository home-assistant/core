"""
Support for Velbus platform.

For more details about this platform, please refer to the documentation at XXX
"""
import asyncio
import logging
import velbus
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

REQUIREMENTS = ['python-velbus==2.0.6']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'velbus'

VELBUS_MESSAGE = 'velbus.message'

CONFIG_MODULE = vol.Schema({
    vol.Required('module'): cv.positive_int,
    vol.Required('channel'): cv.positive_int,
    vol.Required('name'): cv.string,
    vol.Optional('is_pushbutton'): cv.boolean
})

PLATFORM_SCHEMA = vol.Schema({
        vol.Required('serial_port'): cv.string,
        vol.Optional('lights'): vol.All(cv.ensure_list, [CONFIG_MODULE]),
        vol.Optional('switches'): vol.All(cv.ensure_list, [CONFIG_MODULE])
})


@asyncio.coroutine
def async_setup(hass, config):  # noqa: D401
    """Setup the Velbus platform."""
    conf = config.get(DOMAIN)[0]
    device = conf.get('serial_port')

    connection = velbus.VelbusUSBConnection(device)
    controller = velbus.Controller(connection)
    hass.data['VelbusController'] = controller

    @callback
    def stop_velbus(event):
        _LOGGER.debug("Shutting down ")
        connection.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_velbus)

    @callback
    def handle_message(message):
        async_dispatcher_send(hass, VELBUS_MESSAGE, message)

    controller.subscribe(handle_message)

    hass.async_add_job(
        async_load_platform(hass, 'light', DOMAIN, conf['lights'], config)
    )
    hass.async_add_job(
        async_load_platform(hass, 'binary_sensor', DOMAIN, conf['switches'],
                            config)
    )
    return True
