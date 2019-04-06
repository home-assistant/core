"""This module connects to the Genius hub and shares the data."""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_START)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

URL = "https://github.com/zxdavb/geniushub-client/archive/master.zip"
REQUIREMENTS = [URL + '#geniushub-client==0.2.6']                                # TODO: delete me
# REQUIREMENTS = ['geniushub-client==0.2.5']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'geniushub'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Required(CONF_HOST): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, hass_config):
    """Create a Genius Hub system."""
    from geniushubclient import GeniusHubClient

    host = hass_config[DOMAIN].get(CONF_HOST)
    username = hass_config[DOMAIN].get(CONF_USERNAME)
    password = hass_config[DOMAIN].get(CONF_PASSWORD)

    geniushub_data = hass.data[DOMAIN] = {}

    try:
        client = geniushub_data['client'] = GeniusHubClient(
            host, username, password,
            session=async_get_clientsession(hass)
        )

        await client.populate()

        # hub = client.hub
        # zones = await hub.zones
        # discovered = [z for z in zones if z['type'] == 'radiator']

        # hass.async_create_task(async_load_platform(
        #     hass, 'climate', DOMAIN, discovered, hass_config))

        hass.async_create_task(async_load_platform(
            hass, 'climate', DOMAIN, {}, hass_config))

    except AssertionError:  # assert response.status == HTTP_OK, response.text
        _LOGGER.warn(
            "setup(): Failed, check your configuration.",
            exc_info=True)
        return False

    # @callback
    # def _first_update(event):
    #     """When HA has started, the hub knows to retrieve it's first update."""
    #     pkt = {'signal': 'update'}
    #     async_dispatcher_send(hass, DOMAIN, pkt)

    # hass.bus.listen(EVENT_HOMEASSISTANT_START, _first_update)

    _LOGGER.warn("setup(): Finished!")

    return True
