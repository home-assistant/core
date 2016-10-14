"""
Sensor for Steam account status.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.steam_online/
"""
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['steamodd==4.21']

CONF_ACCOUNTS = 'accounts'

ICON = 'mdi:steam'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_ACCOUNTS, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Steam platform."""
    import steam as steamod
    steamod.api.key.set(config.get(CONF_API_KEY))
    add_devices(
        [SteamSensor(account,
                     steamod) for account in config.get(CONF_ACCOUNTS)])


class SteamSensor(Entity):
    """A class for the Steam account."""

    # pylint: disable=abstract-method
    def __init__(self, account, steamod):
        """Initialize the sensor."""
        self._steamod = steamod
        self._account = account
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._profile.persona

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
        self._profile = self._steamod.user.profile(self._account)
        if self._profile.current_game[2] is None:
            self._game = 'None'
        else:
            self._game = self._profile.current_game[2]
        self._state = {
            1: 'Online',
            2: 'Busy',
            3: 'Away',
            4: 'Snooze',
            5: 'Trade',
            6: 'Play',
        }.get(self._profile.status, 'Offline')

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {'Game': self._game}

    @property
    def entity_picture(self):
        """Avatar of the account."""
        return self._profile.avatar_medium

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON
