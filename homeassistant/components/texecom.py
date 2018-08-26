"""
Support for Texecom Alarm Panels & Devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/texecom/
"""

import logging
import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import (async_dispatcher_send)

REQUIREMENTS = ['pyTexecom==0.2.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'texecom'

DATA_EVL = 'texecom'

CONF_PORT = 'port'
CONF_PANEL_TYPE = 'panel_type'
CONF_ZONE_NAME = "name"
CONF_ZONES = 'zones'
CONF_ZONE_TYPE = 'type'
CONF_ZONE_NUMBER = 'zone_number'

DEFAULT_PORT = '/dev/ttys0'
DEFAULT_ZONE_NAME = 'zone'
DEFAULT_ZONE_NUMBER = '1'
DEFAULT_ZONE_TYPE = 'motion'

SIGNAL_ZONE_UPDATE = 'texecom.zones_updated'

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_ZONE_NAME): cv.string,
    vol.Required(CONF_ZONE_TYPE, default=DEFAULT_ZONE_TYPE): cv.string,
    vol.Required(CONF_ZONE_NUMBER, default=DEFAULT_ZONE_NUMBER): cv.string,
    })

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
        vol.Required(CONF_PANEL_TYPE): cv.string,
        vol.Optional(CONF_ZONES): {vol.Coerce(int): ZONE_SCHEMA},
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up for Texecom devices."""
    from pyTexecom import TexecomPanelInterface

    conf = config.get(DOMAIN)
    port = conf.get(CONF_PORT)
    zones = conf.get(CONF_ZONES)
    panel_type = conf.get(CONF_PANEL_TYPE)

    controller = TexecomPanelInterface(
        'Panel Interface', port, panel_type, hass.loop)

    hass.data[DATA_EVL] = controller

    @callback
    def zones_updated_callback(data):
        """Handle zone updates."""
        _LOGGER.debug("Texecom sent a zone update event. Updating zones...")
        async_dispatcher_send(hass, SIGNAL_ZONE_UPDATE, data)

    @callback
    def stop_texecom(event):
        """Shutdown Texecom connection and thread on exit."""
        _LOGGER.info("Shutting down Texecom")
        controller.stop()

    controller.callback_zone_state_change = zones_updated_callback

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_texecom)

    _LOGGER.info("Starting Texecom")
    controller.start()

    # Load sub-components for Texecom
    if zones:
        hass.async_create_task(async_load_platform(
            hass, 'binary_sensor', DOMAIN, {
                CONF_ZONES: zones
            }, config
        ))

    return True
