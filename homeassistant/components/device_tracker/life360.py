"""
Support for the Life360 platform.

For more details about this platform, please refer to the documentation at
TODO
"""
import logging
import requests
import voluptuous as vol

from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_utc_time_change

_LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


def setup_scanner(hass, config, see, discovery_info=None):
    """Validate the configuration and return a Life360 scanner."""
    Life360Scanner(hass, config, see)
    return True


class Life360Scanner(object):
    """A class representing a Life360 scanner."""

    def __init__(self, hass, config, see):
        """Initialize the Life360 scanner."""
        self.hass = hass
        self.see = see

        self.username = config.get(CONF_USERNAME)
        self.password = config.get(CONF_PASSWORD)

        self._update_info()

        track_utc_time_change(
            self.hass, self._update_info, second=range(0, 60, 30))

    def get_members(self):
        """Build members array."""
        # reset member to nothing
        self.members = []

        # get bearer token
        url = 'https://api.life360.com/v3/oauth2/token.json'
        payload = {'grant_type': 'password', 'username': self.username,
                   'password': self.password}
        headers = {'Authorization': 'Basic cFJFcXVnYWJSZXRyZTRFc3RldGhlcnVmc'
                   'mVQdW1hbUV4dWNyRUh1YzptM2ZydXBSZXRSZXN3ZXJFQ2hBUHJFOTZxYW'
                   'tFZHI0Vg=='}
        r = requests.post(url, data=payload, headers=headers,
                          timeout=DEFAULT_TIMEOUT)

        # check if we have valid response
        if r.status_code != 200:
            _LOGGER.error("Incorrect http response while logging in: %s",
                          r.status_code)
            return None

        # hopefully this is working
        try:
            data = r.json()
            self.access_token = data['access_token']
        except:
            _LOGGER.error("Failed to Login")
            self.success_init = False

        _LOGGER.info("Scanning")

        """
        Life360 has the following hierarchy to list devices:
        Account -> Circles -> Members enrolled in Circle.
        """
        # first retrieve the circles
        url = "https://api.life360.com/v3/circles.json"
        headers = {'Content-Type': 'application/json',
                   'Authorization': 'Bearer ' + self.access_token}
        r = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)

        # check if we have valid response
        if r.status_code != 200:
            _LOGGER.error("Incorrect http response while getting circles: %s",
                          r.status_code)
            return None

        # hopefully this is working
        try:
            # put data in json form
            self.circles = r.json()
        except:
            _LOGGER.warning("Cannot get the Life360 Circles")

        if self.circles is not None:
            # yeah! something in the array
            for circle in self.circles['circles']:
                # now get all members per circle
                url = "https://api.life360.com/v3/circles/" + circle['id']
                r = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)

                # check if we have valid response
                if r.status_code != 200:
                    _LOGGER.error("Didn't get a good http response"
                                  "while getting members: %s", r.status_code)
                    return None

                # trying to parse this
                try:
                    data = r.json()
                    for member in data['members']:
                        self.members.append(member)
                except:
                    _LOGGER.warning("Cannot get the Life360 Member")

        if self.members is None:
            _LOGGER.warning("Error using Life360 API")

    def _update_info(self, now=None):
        """Update the device info."""
        _LOGGER.debug("Updating members %s", now)

        # update members
        self.get_members()

        # now notify service that the members are updated
        try:
            for member in self.members:
                # filter members with a location
                if member['features']['device'] == "1":
                    id = member['id']
                    name = member['firstName'] + ' ' + member['lastName']
                    lat = float(member['location']['latitude'])
                    lon = float(member['location']['longitude'])
                    acc = float(member['location']['accuracy'])
                    batt = member['location']['battery']

                    # call function!
                    self.see(
                        mac=id, host_name=name,
                        gps=(lat, lon), gps_accuracy=acc, battery=batt
                    )
        except:
            _LOGGER.warning("Life360 Error while seeing device")
