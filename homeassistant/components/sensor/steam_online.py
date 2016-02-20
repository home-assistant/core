"""
homeassistant.components.sensor.steam_online
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sensor for Steam account status.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.steam_online/
"""
from homeassistant.helpers.entity import Entity
from homeassistant.const import (ATTR_ENTITY_PICTURE, CONF_API_KEY)

ICON = 'mdi:steam'

REQUIREMENTS = ['steamodd==4.21']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Steam platform. """
    import steam as steamod
    steamod.api.key.set(config.get(CONF_API_KEY))
    add_devices(
        [SteamSensor(account,
                     steamod) for account in config.get('accounts', [])])


class SteamSensor(Entity):
    """ Steam account. """

    # pylint: disable=abstract-method
    def __init__(self, account, steamod):
        self._steamod = steamod
        self._account = account
        self.update()

    @property
    def name(self):
        """ Returns the name of the sensor. """
        return self._profile.persona

    @property
    def entity_id(self):
        """ Entity ID. """
        return 'sensor.steam_{}'.format(self._account)

    @property
    def state(self):
        """ State of the sensor. """
        if self._profile.status == 1:
            account_state = 'Online'
        elif self._profile.status == 2:
            account_state = 'Busy'
        elif self._profile.status == 3:
            account_state = 'Away'
        elif self._profile.status == 4:
            account_state = 'Snooze'
        elif self._profile.status == 5:
            account_state = 'Trade'
        elif self._profile.status == 6:
            account_state = 'Play'
        else:
            account_state = 'Offline'
        return account_state

    # pylint: disable=no-member
    def update(self):
        """ Update device state. """
        self._profile = self._steamod.user.profile(self._account)

    @property
    def device_state_attributes(self):
        """ Returns the state attributes. """
        return {
            ATTR_ENTITY_PICTURE: self._profile.avatar_medium
        }

    @property
    def icon(self):
        """ Icon to use in the frontend """
        return ICON
