"""
Support for OpenTherm Gateway devices.

For more details about this component, please refer to the documentation at
http://home-assistant.io/components/opentherm_gw/
"""
import logging

import voluptuous as vol

from homeassistant.const import (CONF_DEVICE, CONF_NAME, PRECISION_HALVES,
                                 PRECISION_TENTHS, PRECISION_WHOLE)
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

import homeassistant.helpers.config_validation as cv

DOMAIN = 'opentherm_gw'

CONF_CLIMATE = 'climate'
CONF_FLOOR_TEMP = 'floor_temperature'
CONF_PRECISION = 'precision'

DATA_DEVICE = 'device'
DATA_GW_VARS = 'gw_vars'
DATA_OPENTHERM_GW = 'opentherm_gw'

SIGNAL_OPENTHERM_GW_UPDATE = 'opentherm_gw_update'

CLIMATE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default="OpenTherm Gateway"): cv.string,
    vol.Optional(CONF_PRECISION): vol.In([PRECISION_TENTHS, PRECISION_HALVES,
                                          PRECISION_WHOLE]),
    vol.Optional(CONF_FLOOR_TEMP, default=False): cv.boolean,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_CLIMATE, default={}): CLIMATE_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)

REQUIREMENTS = ['pyotgw==0.1b0']

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the OpenTherm Gateway component."""
    import pyotgw
    conf = config[DOMAIN]
    gateway = pyotgw.pyotgw()
    hass.data[DATA_OPENTHERM_GW] = {
        DATA_DEVICE: gateway,
        DATA_GW_VARS: pyotgw.vars,
    }
    hass.async_create_task(connect_and_subscribe(
        hass, conf[CONF_DEVICE], gateway))
    hass.async_create_task(async_load_platform(
        hass, 'climate', DOMAIN, conf.get(CONF_CLIMATE)))
    return True


async def connect_and_subscribe(hass, device_path, gateway):
    """Connect to serial device and subscribe report handler."""
    await gateway.connect(hass.loop, device_path)
    _LOGGER.debug("Connected to OpenTherm Gateway at %s", device_path)

    async def handle_report(status):
        """Handle reports from the OpenTherm Gateway."""
        _LOGGER.debug("Received report: %s", status)
        async_dispatcher_send(hass, SIGNAL_OPENTHERM_GW_UPDATE, status)
    gateway.subscribe(handle_report)
