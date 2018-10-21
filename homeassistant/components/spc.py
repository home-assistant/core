"""
Support for Vanderbilt (formerly Siemens) SPC alarm systems.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/spc/
"""
import logging

import voluptuous as vol

from homeassistant.helpers import discovery, aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyspcwebgw==0.4.0']

_LOGGER = logging.getLogger(__name__)

CONF_WS_URL = 'ws_url'
CONF_API_URL = 'api_url'

DOMAIN = 'spc'
DATA_API = 'spc_api'

SIGNAL_UPDATE_ALARM = 'spc_update_alarm_{}'
SIGNAL_UPDATE_SENSOR = 'spc_update_sensor_{}'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_WS_URL): cv.string,
        vol.Required(CONF_API_URL): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the SPC component."""
    from pyspcwebgw import SpcWebGateway

    async def async_upate_callback(spc_object):
        from pyspcwebgw.area import Area
        from pyspcwebgw.zone import Zone

        if isinstance(spc_object, Area):
            async_dispatcher_send(hass,
                                  SIGNAL_UPDATE_ALARM.format(spc_object.id))
        elif isinstance(spc_object, Zone):
            async_dispatcher_send(hass,
                                  SIGNAL_UPDATE_SENSOR.format(spc_object.id))

    session = aiohttp_client.async_get_clientsession(hass)

    spc = SpcWebGateway(loop=hass.loop, session=session,
                        api_url=config[DOMAIN].get(CONF_API_URL),
                        ws_url=config[DOMAIN].get(CONF_WS_URL),
                        async_callback=async_upate_callback)

    hass.data[DATA_API] = spc

    if not await spc.async_load_parameters():
        _LOGGER.error('Failed to load area/zone information from SPC.')
        return False

    # add sensor devices for each zone (typically motion/fire/door sensors)
    hass.async_create_task(discovery.async_load_platform(
        hass, 'binary_sensor', DOMAIN, {}))

    # create a separate alarm panel for each area
    hass.async_create_task(discovery.async_load_platform(
        hass, 'alarm_control_panel', DOMAIN, {}))

    # start listening for incoming events over websocket
    spc.start()

    return True
