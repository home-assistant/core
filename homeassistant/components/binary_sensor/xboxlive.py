"""
Sensor for Xbox Live account status.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.xbox_live/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, STATE_UNKNOWN
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)

REQUIREMENTS = ['xbox==0.1.3']

_LOGGER = logging.getLogger(__name__)

CONF_XUIDS = 'xuids'
CONF_GAMERTAGS = 'gamertags'

ICON = 'mdi:xbox'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_XUIDS): vol.All(cv.ensure_list, [cv.positive_int]),
    vol.Required(CONF_GAMERTAGS): vol.All(cv.ensure_list, [cv.string]),
})


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Xbox platform."""
    import xbox
    xbox.client.authenticate(login=config.get(CONF_USERNAME),
                             password=config.get(CONF_PASSWORD))
    devices = []

    for xuid in config.get(CONF_XUIDS):
        try:
            gamer_profile = xbox.GamerProfile.from_xuid(xuid)
        except xbox.exceptions.GamertagNotFound:
            _LOGGER.error("Can not found Xbox UID %s", xuid)
            continue
        devices.append(XboxSensor(hass, gamer_profile))

    for gamertag in config.get(CONF_GAMERTAGS):
        try:
            gamer_profile = xbox.GamerProfile.from_gamertag(gamertag)
        except xbox.exceptions.GamertagNotFound:
            _LOGGER.error("Can not found Gamertag %s", gamertag)
            continue
        devices.append(XboxSensor(hass, gamer_profile))

    if devices:
        add_devices(devices)
    else:
        return False


class XboxSensor(BinarySensorDevice):
    """A class for the Xbox account."""

    def __init__(self, hass, gamer_profile):
        """Initialize the sensor."""
        self._hass = hass
        self._state = STATE_UNKNOWN
        self._gamer_profile = gamer_profile
        self._gamertag = gamer_profile.gamertag
        self._gamerscore = None
        self._devices = []
        self._xuid = gamer_profile.xuid
        self._picture = gamer_profile.gamerpic
        self._headers = {
            'x-xbl-contract-version': '2',
            'User-Agent': ('XboxRecord.Us Like SmartGlass/2.105.0415 '
                           'CFNetwork/711.3.18 Darwin/14.0.0')}

    @property
    def name(self):
        """Return the name of the sensor."""
        return "xboxlive_{}".format(self._gamertag)

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state == 'online'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            "xuid": self._xuid,
            "gamerscore": self._gamerscore,
        }
        for device in self._devices:
            for title in device.get('titles'):
                attributes[
                    '{}_{}'.format(device.get('type').lower(),
                                   title.get('placement').lower())
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

    @asyncio.coroutine
    def async_update(self):
        """Update state data from Xbox API."""
        import xbox
        # TODO check of client is connected
        # Get profile
        gamer_profile = xbox.GamerProfile.from_xuid(self._xuid)
        self._gamer_profile = gamer_profile
        self._gamertag = gamer_profile.gamertag
        self._picture = gamer_profile.gamerpic

        # Get presence
        url = "https://userpresence.xboxlive.com/users/batch"
        data = {"users": [self._xuid], "level": "all"}
        response = xbox.client._post_json(url, data=data,
                                          headers=self._headers)
        if response.status_code != 200:
            _LOGGER.error("Can not get %s presence", self._gamertag)
            return
        results = response.json()
        if len(results) != 1:
            _LOGGER.error("Can not get %s presence", self._gamertag)
            return

        # Save state
        self._state = results[0].get('state', STATE_UNKNOWN).lower()
        # Save devices
        self._devices = results[0].get('devices', [])

        # Get Other data
        url = "https://profile.xboxlive.com/users/batch/profile/settings"
        settings = ["Gamertag", "RealName", "Bio", "Location", "Gamerscore",
                    "GameDisplayPicRaw", "AccountTier", "XboxOneRep",
                    "PreferredColor"]
        data = {"userIds": [self._xuid], "settings": settings}
        response = xbox.client._post_json(url, data=data,
                                          headers=self._headers)
        if response.status_code != 200:
            _LOGGER.error("Can not get %s presence", self._gamertag)
            return

        profiles = response.json().get('profileUsers', [])
        if len(profiles) != 1:
            _LOGGER.error("Can not get %s presence", self._gamertag)
            return

        for setting in profiles[0].get('settings', []):
            if setting.get('id') == 'Gamerscore':
                self._gamerscore = int(setting.get('value'))
