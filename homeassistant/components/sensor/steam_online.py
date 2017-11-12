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

STATE_ONLINE = 'Online'
STATE_BUSY = 'Busy'
STATE_AWAY = 'Away'
STATE_SNOOZE = 'Snooze'
STATE_TRADE = 'Trade'
STATE_PLAY = 'Play'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_ACCOUNTS, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Steam platform."""
    import steam as steamod
    steamod.api.key.set(config.get(CONF_API_KEY))
    add_devices(
        [SteamSensor(account,
                     steamod) for account in config.get(CONF_ACCOUNTS)], True)


class SteamSensor(Entity):
    """A class for the Steam account."""

    def __init__(self, account, steamod):
        """Initialize the sensor."""
        self._steamod = steamod
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

    # pylint: disable=no-member
    def update(self):
        """Update device state."""
        try:
            self._profile = self._steamod.user.profile(self._account)
            if self._profile.current_game[2] is None:
                self._game = 'None'
            else:
                self._game = self._profile.current_game[2]
            self._state = {
                1: STATE_ONLINE,
                2: STATE_BUSY,
                3: STATE_AWAY,
                4: STATE_SNOOZE,
                5: STATE_TRADE,
                6: STATE_PLAY,
            }.get(self._profile.status, 'Offline')
            self._name = self._profile.persona
            self._avatar = self._profile.avatar_medium
        except self._steamod.api.HTTPTimeoutError as error:
            _LOGGER.warning(error)
            self._game = self._state = self._name = self._avatar = None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {'game': self._game}

    @property
    def entity_picture(self):
        """Avatar of the account."""
        return self._avatar

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON
