"""
Support Hook, available at hooksmarthome.com

Controls RF switches like these:  https://www.amazon.com/Etekcity-Wireless-Electrical-Household-Appliances/dp/B00DQELHBS

There is no way to query for state or success of commands

"""
import logging
import requests

import voluptuous as vol

from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

HOOK_ENDPOINT = "https://api.gethook.io/v1/"
TIMEOUT = 10

SWITCH_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Hook by getting the access token and list of actions"""

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        response = requests.post(HOOK_ENDPOINT + 'user/login', data = {'username': username, 'password': password}, timeout = TIMEOUT)
        data = response.json()
    except (requests.exceptions.RequestException, ValueError) as error:
        _LOGGER.error("Failed authentication API call: %s", error)
        return False
    
    try:
        token = data['data']['token']
    except KeyError:
        _LOGGER.error("No token. Check username and password")
        return False
	
    try:
        response = requests.get(HOOK_ENDPOINT + 'device', params = {"token": data['data']['token']})
        data = response.json()
    except (requests.exceptions.RequestException, ValueError) as error:
        _LOGGER.error("Failed getting devices: %s", error)
        return False

    add_devices(HookSmartHome(hass, token, d['device_id'], d['device_name']) for lst in data['data'] for d in lst)


class HookSmartHome(SwitchDevice):
    """Representation of a Hook device, allowing on and off commands."""

    # pylint: disable=too-many-arguments
    def __init__(self, hass, token, device_id, device_name):
        """Initialize the switch."""
        self._hass = hass
        self._token = token
        self._state = False
        self._id = device_id
        self._name = device_name
        _LOGGER.debug("Creating Hook object: ID: " + self._id + " Name: " + self._name)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        _LOGGER.debug("Turning on: %s", self._name)
        requests.get(HOOK_ENDPOINT + 'device/trigger/' + self._id + '/On', params = {"token": self._token})
        self._state = True

    def turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGER.debug("Turning on: %s", self._name)
        requests.get(HOOK_ENDPOINT + 'device/trigger/' + self._id + '/Off', params = {"token": self._token})
        self._state = False
