"""
Support for Harmony Hub devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/remote.harmony/

"""

import logging
from homeassistant.const import CONF_NAME, CONF_HOST, \
    CONF_PORT
from homeassistant.components.remote import PLATFORM_SCHEMA
from homeassistant.util import slugify
import homeassistant.components.remote as remote
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

REQUIREMENTS = ['pyharmony==1.0.12']
_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = 'device'
ATTR_COMMAND = 'command'
ATTR_ACTIVITY = 'activity'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.string,
    vol.Required(ATTR_ACTIVITY, default='Not_Set'): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Harmony platform."""
    import pyharmony
    import urllib.parse
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    _LOGGER.info('Loading Harmony platform: ' + name)

    harmony_conf_file = hass.config.path('harmony_' + slugify(name) + '.conf')

    try:
        _LOGGER.debug('calling pyharmony.ha_get_token for remote at: ' +
                      host + ':' + port)
        token = urllib.parse.quote_plus(pyharmony.ha_get_token(host, port))
    except ValueError as err:
        _LOGGER.critical(err.args[0] + ' for remote: ' + name)
        return False

    _LOGGER.debug('received token: ' + token)
    add_devices([HarmonyRemote(config.get(CONF_NAME),
                               config.get(CONF_HOST),
                               config.get(CONF_PORT),
                               config.get(ATTR_ACTIVITY),
                               harmony_conf_file,
                               token)])
    return True


class HarmonyRemote(remote.RemoteDevice):
    """Remote representation used to control a Harmony device."""

    def __init__(self, name, host, port, activity, path, token):
        """Initialize HarmonyRemote class."""

        import pyharmony
        from pathlib import Path

        _LOGGER.debug('HarmonyRemote device init started for: ' + name)
        self._name = name
        self._ip = host
        self._port = port
        self._state = None
        self._current_activity = None
        self._default_activity = activity
        self._token = token
        self._config_path = path
        _LOGGER.debug('retrieving harmony config using token: ' + token)
        self._config = pyharmony.ha_get_config(self.token, host, port)
        if not Path(self._config_path).is_file():
            _LOGGER.debug('writing harmony configuration to file: ' + path)
            pyharmony.ha_write_config_file(self._config, self._config_path)

    @property
    def name(self):
        """Return the Harmony device's name."""
        return self._name

    @property
    def token(self):
        """Return the token of the Harmony device."""
        return self._token

    @property
    def config(self):
        """Return the configuration of the Harmony device."""
        return self._config

    @property
    def device_state_attributes(self):
        """Add platform specific attributes."""
        return {'current_activity': self._current_activity}

    @property
    def is_on(self):
        """Return False if PowerOff is the current activity, otherwise True."""
        return self._current_activity != 'PowerOff'

    def update(self):
        """Return current activity."""
        import pyharmony
        name = self._name
        _LOGGER.debug('polling ' + name + ' for current activity')
        state = pyharmony.ha_get_current_activity(self._token,
                                                  self._config,
                                                  self._ip,
                                                  self._port)
        _LOGGER.debug(name + '\'s current activity reported as: ' + state)
        self._current_activity = state
        self._state = bool(state != 'PowerOff')

    def turn_on(self, **kwargs):
        """Start an activity from the Harmony device."""
        import pyharmony
        if kwargs[ATTR_ACTIVITY]:
            activity = kwargs[ATTR_ACTIVITY]
        else:
            activity = self._default_activity

        if activity != 'Not_Set':
            pyharmony.ha_start_activity(self._token,
                                        self._ip,
                                        self._port,
                                        self._config,
                                        activity)
            self._state = True
        else:
            _LOGGER.error('No activity specified with turn_on service')

    def turn_off(self):
        """Start the PowerOff activity."""
        import pyharmony
        pyharmony.ha_power_off(self._token, self._ip, self._port)

    def send_command(self, **kwargs):
        """Send a command to one device."""
        import pyharmony
        pyharmony.ha_send_command(self._token, self._ip,
                                  self._port, kwargs[ATTR_DEVICE],
                                  kwargs[ATTR_COMMAND])

    def sync(self):
        """Sync the Harmony device with the web service."""
        import pyharmony
        _LOGGER.debug('syncing hub with Harmony servers')
        pyharmony.ha_sync(self._token, self._ip, self._port)
        self._config = pyharmony.ha_get_config(self._token,
                                               self._ip,
                                               self._port)
        _LOGGER.debug('writing hub config to file: ' + self._config_path)
        pyharmony.ha_write_config_file(self._config, self._config_path)
