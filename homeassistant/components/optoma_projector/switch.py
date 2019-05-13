"""
Use Optoma's Web interface to control the projector.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/switch.optoma_projector/
"""
import logging
from urllib import parse
import hashlib
import requests
from bs4 import BeautifulSoup
import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_USERNAME, CONF_PASSWORD)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Optoma Projector'
ICON = 'mdi:projector'
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'admin'
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Return an Optoma Projector."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    add_entities([OptomaSwitch(host, name, username, password)], True)


class OptomaSwitch(SwitchDevice):
    """Represents an Optoma Projector as a switch."""

    def __init__(self, host, name, username, password, **kwargs):
        """Init of the Optoma projector."""
        self.url = 'http://'+host
        self._name = name
        self.username = username
        self.password = password
        self.session = requests.session()
        self._state = False
        self._login()

    def _login(self):
        response = self.session.get(parse.urljoin(self.url, '/login.htm'))
        html = BeautifulSoup(response.text, 'html.parser')
        challenge = html.find('input', {'name': 'Challenge'})['value']
        login_str = self.username+self.password+challenge
        response = hashlib.md5(login_str.encode())

        data = {
            'user': 0,
            'Username': '1',
            'Password': '',
            'Challenge': '',
            'Response': response.hexdigest(),
        }
        self.session.post(parse.urljoin(self.url, '/tgi/login.tgi'), data)

    @property
    def name(self):
        """Return name of the projector."""
        return self._name

    @property
    def is_on(self):
        """Return if the projector is turned on."""
        return self._state

    def update(self):
        """Get the latest state from the projector."""
        response = self.session.get(parse.urljoin(self.url, '/control.htm'))
        html = BeautifulSoup(response.text, 'html.parser')
        power_status = int(html.find("input", {"id": "pwr"})['value'])
        if power_status == 1:
            self._state = True
        else:
            self._state = False

    def turn_on(self, **kwargs):
        """Turn the projector on."""
        on_command = {
            'btn_powon': 'Power On'
        }
        self.session.post(parse.urljoin(self.url, '/tgi/control.tgi'), on_command)
        self._state = True

    def turn_off(self, **kwargs):
        """Turn the projector off."""
        off_command = {
            'btn_powoff': 'Power Off'
        }
        self.session.post(parse.urljoin(self.url, '/tgi/control.tgi'), off_command)
        self._state = False
