"""
Support for Tile® Bluetooth trackers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.tile/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_USERNAME, CONF_MONITORED_VARIABLES, CONF_PASSWORD)
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.util import slugify
from homeassistant.util.json import load_json, save_json

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pytile==1.1.0']

CLIENT_UUID_CONFIG_FILE = '.tile.conf'
DEFAULT_ICON = 'mdi:bluetooth'
DEVICE_TYPES = ['PHONE', 'TILE']

ATTR_ALTITUDE = 'altitude'
ATTR_CONNECTION_STATE = 'connection_state'
ATTR_IS_DEAD = 'is_dead'
ATTR_IS_LOST = 'is_lost'
ATTR_RING_STATE = 'ring_state'
ATTR_VOIP_STATE = 'voip_state'

CONF_SHOW_INACTIVE = 'show_inactive'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SHOW_INACTIVE, default=False): cv.boolean,
    vol.Optional(CONF_MONITORED_VARIABLES):
        vol.All(cv.ensure_list, [vol.In(DEVICE_TYPES)]),
})


def setup_scanner(hass, config: dict, see, discovery_info=None):
    """Validate the configuration and return a Tile scanner."""
    TileDeviceScanner(hass, config, see)
    return True


class TileDeviceScanner(DeviceScanner):
    """Define a device scanner for Tiles."""

    def __init__(self, hass, config, see):
        """Initialize."""
        from pytile import Client

        _LOGGER.debug('Received configuration data: %s', config)

        # Load the client UUID (if it exists):
        config_data = load_json(hass.config.path(CLIENT_UUID_CONFIG_FILE))
        if config_data:
            _LOGGER.debug('Using existing client UUID')
            self._client = Client(
                config[CONF_USERNAME],
                config[CONF_PASSWORD],
                config_data['client_uuid'])
        else:
            _LOGGER.debug('Generating new client UUID')
            self._client = Client(
                config[CONF_USERNAME],
                config[CONF_PASSWORD])

            if not save_json(
                    hass.config.path(CLIENT_UUID_CONFIG_FILE),
                    {'client_uuid': self._client.client_uuid}):
                _LOGGER.error("Failed to save configuration file")

        _LOGGER.debug('Client UUID: %s', self._client.client_uuid)
        _LOGGER.debug('User UUID: %s', self._client.user_uuid)

        self._show_inactive = config.get(CONF_SHOW_INACTIVE)
        self._types = config.get(CONF_MONITORED_VARIABLES)

        self.devices = {}
        self.see = see

        track_utc_time_change(
            hass, self._update_info, second=range(0, 60, 30))

        self._update_info()

    def _update_info(self, now=None) -> None:
        """Update the device info."""
        self.devices = self._client.get_tiles(
            type_whitelist=self._types, show_inactive=self._show_inactive)

        if not self.devices:
            _LOGGER.warning('No Tiles found')
            return

        for dev in self.devices:
            dev_id = 'tile_{0}'.format(slugify(dev['name']))
            lat = dev['tileState']['latitude']
            lon = dev['tileState']['longitude']

            attrs = {
                ATTR_ALTITUDE: dev['tileState']['altitude'],
                ATTR_CONNECTION_STATE: dev['tileState']['connection_state'],
                ATTR_IS_DEAD: dev['is_dead'],
                ATTR_IS_LOST: dev['tileState']['is_lost'],
                ATTR_RING_STATE: dev['tileState']['ring_state'],
                ATTR_VOIP_STATE: dev['tileState']['voip_state'],
            }

            self.see(
                dev_id=dev_id,
                gps=(lat, lon),
                attributes=attrs,
                icon=DEFAULT_ICON
            )
