"""
Sensor for Steam account status.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.steam_online/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['steamodd==4.21']

_LOGGER = logging.getLogger(__name__)

CONF_ACCOUNTS = 'accounts'

ICON = 'mdi:steam'

STATE_OFFLINE = 'offline'
STATE_ONLINE = 'online'
STATE_BUSY = 'busy'
STATE_AWAY = 'away'
STATE_SNOOZE = 'snooze'
STATE_LOOKING_TO_TRADE = 'looking_to_trade'
STATE_LOOKING_TO_PLAY = 'looking_to_play'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_ACCOUNTS, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Steam platform."""
    import steam as steamod
    steamod.api.key.set(config.get(CONF_API_KEY))
    # Initialize steammods app list before creating sensors
    # to benefit from internal caching of the list.
    steam_app_list = steamod.apps.app_list()
    add_entities(
        [SteamSensor(account,
                     steamod,
                     steam_app_list)
         for account in config.get(CONF_ACCOUNTS)], True)


class SteamSensor(Entity):
    """A class for the Steam account."""

    def __init__(self, account, steamod, steam_app_list):
        """Initialize the sensor."""
        self._steamod = steamod
        self._steam_app_list = steam_app_list
        self._account = account
        self._profile = None
        self._game = self._state = self._name = self._avatar = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def entity_id(self):
        """Return the entity ID."""
        return 'sensor.steam_{}'.format(self._account)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update device state."""
        try:
            self._profile = self._steamod.user.profile(self._account)
            self._game = self._get_current_game()
            self._state = {
                1: STATE_ONLINE,
                2: STATE_BUSY,
                3: STATE_AWAY,
                4: STATE_SNOOZE,
                5: STATE_LOOKING_TO_TRADE,
                6: STATE_LOOKING_TO_PLAY,
            }.get(self._profile.status, STATE_OFFLINE)
            self._name = self._profile.persona
            self._avatar = self._profile.avatar_medium
        except self._steamod.api.HTTPTimeoutError as error:
            _LOGGER.warning(error)
            self._game = self._state = self._name = self._avatar = None

    def _get_current_game(self):
        game_id = self._profile.current_game[0]
        game_extra_info = self._profile.current_game[2]

        if game_extra_info:
            return game_extra_info

        if game_id and game_id in self._steam_app_list:
            # The app list always returns a tuple
            # with the game id and the game name
            return self._steam_app_list[game_id][1]

        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {'game': self._game} if self._game else None

    @property
    def entity_picture(self):
        """Avatar of the account."""
        return self._avatar

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON
