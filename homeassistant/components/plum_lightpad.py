"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/plum_lightpad
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['plumlightpad==0.0.11']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'plum_lightpad'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

PLUM_DATA = 'plum'


async def async_setup(hass, config):
    """Plum Lightpad Platform initialization."""
    from plumlightpad import Plum

    conf = config[DOMAIN]
    plum = Plum(conf[CONF_USERNAME], conf[CONF_PASSWORD])

    hass.data[PLUM_DATA] = plum

    def cleanup(event):
        """Clean up resources."""
        plum.cleanup()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)

    cloud_web_sesison = async_get_clientsession(hass, verify_ssl=True)
    await plum.loadCloudData(cloud_web_sesison)

    async def new_load(device):
        """Load light and sensor platforms when LogicalLoad is detected."""
        await asyncio.wait([
            hass.async_create_task(
                discovery.async_load_platform(
                    hass, 'light', DOMAIN,
                    discovered=device, hass_config=conf))
        ])

    async def new_lightpad(device):
        """Load light and binary sensor platforms when Lightpad detected."""
        await asyncio.wait([
            hass.async_create_task(
                discovery.async_load_platform(
                    hass, 'light', DOMAIN,
                    discovered=device, hass_config=conf))
        ])

    device_web_session = async_get_clientsession(hass, verify_ssl=False)
    hass.async_create_task(
        plum.discover(hass.loop,
                      loadListener=new_load, lightpadListener=new_lightpad,
                      websession=device_web_session))

    return True
