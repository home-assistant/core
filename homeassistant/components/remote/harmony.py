"""
Support for Harmony Hub devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/remote.harmony/

"""

import logging
from homeassistant.const import CONF_NAME, CONF_USERNAME, \
                                CONF_PASSWORD, CONF_HOST, \
                                CONF_PORT, STATE_OFF, STATE_ON
from homeassistant.components.remote import PLATFORM_SCHEMA
from homeassistant.util import slugify
import homeassistant.components.remote as remote
import homeassistant.helpers.config_validation as cv
import pyharmony
import voluptuous as vol


REQUIREMENTS = ['pyharmony>=1.0.9']
_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = 'device'
ATTR_COMMAND = 'command'
ATTR_ACTIVITY = 'activity'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.string,
    vol.Optional(ATTR_ACTIVITY, default='Not_Set'): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Harmony platform."""
    name = config.get(CONF_NAME)
    _LOGGER.info('Loading Harmony component: ' + name)

    harmony_conf_file = hass.config.path('harmony_' + slugify(name) + '.conf')

    try:
        token = pyharmony.ha_get_token(config.get(CONF_USERNAME),
                                       config.get(CONF_PASSWORD))
    except ValueError as err:
        print(err.args[0], 'for remote:', config.get(CONF_NAME))
        return False

    add_devices([HarmonyRemote(config.get(CONF_NAME),
                               config.get(CONF_USERNAME),
                               config.get(CONF_PASSWORD),
                               config.get(CONF_HOST),
                               config.get(CONF_PORT),
                               config.get(ATTR_ACTIVITY),
                               harmony_conf_file,
                               token)])
    return True


class HarmonyRemote(remote.RemoteDevice):
    """Remote representation used to control a Harmony device."""

    def __init__(self, name, username, pw, host, port, activity, path, token):
        """Initialize HarmonyRemote class."""
        self._name = name
        self._email = username
        self._password = pw
        self._ip = host
        self._port = port
        self._state = None
        self._current_activity = None
        self._default_activity = activity
        self._token = token
        self._config = pyharmony.ha_get_config(self.token, host, port)
        pyharmony.ha_get_config_file(self._config, path)

    @property
    def name(self):
        """Return the Harmony device's name."""
        return self._name

    @property
    def state(self):
        """Return the state of the Harmony device."""
        return self._state

    @property
    def token(self):
        """Return the token of the Harmony device."""
        return self._token

    @property
    def config(self):
        """Return the configuration of the Harmony device."""
        return self._config

    @property
    def state_attributes(self):
        """Overwrite inherited attributes."""
        return {'current_activity': self._current_activity}

    def is_on(self):
        """Return False if PowerOff is the current activity, otherwise true."""
        return self.update()

    def update(self):
        """Return current activity."""
        state = pyharmony.ha_get_current_activity(self._token,
                                                  self._config,
                                                  self._ip,
                                                  self._port)
        self._current_activity = state
        if state != 'PowerOff':
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

    def turn_on(self, **kwargs):
        """Start an activity from the Harmony device."""
        if not kwargs[ATTR_ACTIVITY]:
            activity = self._default_activity
        else:
            activity = kwargs[ATTR_ACTIVITY]

        pyharmony.ha_start_activity(self._token,
                                    self._ip,
                                    self._port,
                                    self._config,
                                    activity)
        self._state = STATE_ON

    def turn_off(self):
        """Start the PowerOff activity."""
        pyharmony.ha_power_off(self._token, self._ip, self._port)

    def send_command(self, **kwargs):
        """Send a command to one device."""
        pyharmony.ha_send_command(self._token, self._ip,
                                  self._port, kwargs[ATTR_DEVICE],
                                  kwargs[ATTR_COMMAND])

    def sync(self):
        """Sync the Harmony device with the web service."""
        pyharmony.ha_sync(self._token, self._ip, self._port)
