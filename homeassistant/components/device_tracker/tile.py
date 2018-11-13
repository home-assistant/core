"""
Support for Tile® Bluetooth trackers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.tile/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_USERNAME, CONF_MONITORED_VARIABLES, CONF_PASSWORD)
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import slugify
from homeassistant.util.json import load_json, save_json

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['pytile==2.0.5']

CLIENT_UUID_CONFIG_FILE = '.tile.conf'
DEVICE_TYPES = ['PHONE', 'TILE']

ATTR_ALTITUDE = 'altitude'
ATTR_CONNECTION_STATE = 'connection_state'
ATTR_IS_DEAD = 'is_dead'
ATTR_IS_LOST = 'is_lost'
ATTR_RING_STATE = 'ring_state'
ATTR_VOIP_STATE = 'voip_state'
ATTR_TILE_ID = 'tile_identifier'
ATTR_TILE_NAME = 'tile_name'

CONF_SHOW_INACTIVE = 'show_inactive'

DEFAULT_ICON = 'mdi:view-grid'
DEFAULT_SCAN_INTERVAL = timedelta(minutes=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SHOW_INACTIVE, default=False): cv.boolean,
    vol.Optional(CONF_MONITORED_VARIABLES, default=DEVICE_TYPES):
        vol.All(cv.ensure_list, [vol.In(DEVICE_TYPES)]),
})


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Validate the configuration and return a Tile scanner."""
    from pytile import Client

    websession = aiohttp_client.async_get_clientsession(hass)

    config_file = hass.config.path(".{}{}".format(
        slugify(config[CONF_USERNAME]), CLIENT_UUID_CONFIG_FILE))
    config_data = await hass.async_add_job(
        load_json, config_file)
    if config_data:
        client = Client(
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            websession,
            client_uuid=config_data['client_uuid'])
    else:
        client = Client(
            config[CONF_USERNAME], config[CONF_PASSWORD], websession)

        config_data = {'client_uuid': client.client_uuid}
        await hass.async_add_job(save_json, config_file, config_data)

    scanner = TileScanner(
        client, hass, async_see, config[CONF_MONITORED_VARIABLES],
        config[CONF_SHOW_INACTIVE])
    return await scanner.async_init()


class TileScanner:
    """Define an object to retrieve Tile data."""

    def __init__(self, client, hass, async_see, types, show_inactive):
        """Initialize."""
        self._async_see = async_see
        self._client = client
        self._hass = hass
        self._show_inactive = show_inactive
        self._types = types

    async def async_init(self):
        """Further initialize connection to the Tile servers."""
        from pytile.errors import TileError

        try:
            await self._client.async_init()
        except TileError as err:
            _LOGGER.error('Unable to set up Tile scanner: %s', err)
            return False

        await self._async_update()

        async_track_time_interval(
            self._hass, self._async_update, DEFAULT_SCAN_INTERVAL)

        return True

    async def _async_update(self, now=None):
        """Update info from Tile."""
        from pytile.errors import SessionExpiredError, TileError

        _LOGGER.debug('Updating Tile data')

        try:
            await self._client.async_init()
            tiles = await self._client.tiles.all(
                whitelist=self._types, show_inactive=self._show_inactive)
        except SessionExpiredError:
            _LOGGER.info('Session expired; trying again shortly')
            return
        except TileError as err:
            _LOGGER.error('There was an error while updating: %s', err)
            return

        if not tiles:
            _LOGGER.warning('No Tiles found')
            return

        for tile in tiles:
            await self._async_see(
                dev_id='tile_{0}'.format(slugify(tile['tile_uuid'])),
                gps=(
                    tile['tileState']['latitude'],
                    tile['tileState']['longitude']
                ),
                attributes={
                    ATTR_ALTITUDE: tile['tileState']['altitude'],
                    ATTR_CONNECTION_STATE:
                        tile['tileState']['connection_state'],
                    ATTR_IS_DEAD: tile['is_dead'],
                    ATTR_IS_LOST: tile['tileState']['is_lost'],
                    ATTR_RING_STATE: tile['tileState']['ring_state'],
                    ATTR_VOIP_STATE: tile['tileState']['voip_state'],
                    ATTR_TILE_ID: tile['tile_uuid'],
                    ATTR_TILE_NAME: tile['name']
                },
                icon=DEFAULT_ICON)
