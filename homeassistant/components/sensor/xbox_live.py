"""
Sensor for Xbox Live account status.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.xbox_live/
"""
import logging
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_API_KEY, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:xbox'

REQUIREMENTS = ['xboxapi==0.1.1']

CONF_XUID = 'xuid'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_XUID): vol.All(cv.ensure_list, [cv.string])
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Xbox platform."""
    from xboxapi import xbox_api
    api = xbox_api.XboxApi(config.get(CONF_API_KEY))
    devices = []

    for xuid in config.get(CONF_XUID):
        new_device = XboxSensor(hass, api, xuid)
        if new_device.success_init:
            devices.append(new_device)

    if len(devices) > 0:
        add_devices(devices)
    else:
        return False


# pylint: disable=too-many-instance-attributes
class XboxSensor(Entity):
    """A class for the Xbox account."""

    def __init__(self, hass, api, xuid):
        """Initialize the sensor."""
        self._hass = hass
        self._state = STATE_UNKNOWN
        self._presence = {}
        self._xuid = xuid
        self._api = api

        # get profile info
        profile = self._api.get_user_profile(self._xuid)

        if profile.get('success', True) \
                and profile.get('code', 0) != 28:
            self.success_init = True
            self._gamertag = profile.get('Gamertag')
            self._picture = profile.get('GameDisplayPicRaw')
        else:
            self.success_init = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._gamertag

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {}
        for device in self._presence:
            for title in device.get('titles'):
                attributes[
                    '{} {}'.format(device.get('type'),
                                   title.get('placement'))
                ] = title.get('name')

        return attributes

    @property
    def entity_picture(self):
        """Avatar of the account."""
        return self._picture

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON

    def update(self):
        """Update state data from Xbox API."""
        presence = self._api.get_user_presence(self._xuid)
        self._state = presence.get('state', STATE_UNKNOWN)
        self._presence = presence.get('devices', {})
