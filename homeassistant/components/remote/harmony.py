"""
Support for Harmony Hub devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/remote.harmony/
"""
import logging
from os import path
import urllib.parse

import voluptuous as vol

import homeassistant.components.remote as remote
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, ATTR_ENTITY_ID)
from homeassistant.components.remote import (
    PLATFORM_SCHEMA, DOMAIN, ATTR_DEVICE, ATTR_COMMAND,
    ATTR_ACTIVITY, ATTR_NUM_REPEATS, ATTR_DELAY_SECS)
from homeassistant.util import slugify
from homeassistant.config import load_yaml_config_file

REQUIREMENTS = ['pyharmony==1.0.16']

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 5222
DEVICES = []

SERVICE_SYNC = 'harmony_sync'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(ATTR_ACTIVITY, default=None): cv.string,
})

HARMONY_SYNC_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Harmony platform."""
    import pyharmony
    global DEVICES

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    _LOGGER.debug("Loading Harmony platform: %s", name)

    harmony_conf_file = hass.config.path(
        '{}{}{}'.format('harmony_', slugify(name), '.conf'))

    try:
        _LOGGER.debug("Calling pyharmony.ha_get_token for remote at: %s:%s",
                      host, port)
        token = urllib.parse.quote_plus(pyharmony.ha_get_token(host, port))
    except ValueError as err:
        _LOGGER.warning("%s for remote: %s", err.args[0], name)
        return False

    _LOGGER.debug("Received token: %s", token)
    DEVICES = [HarmonyRemote(
        config.get(CONF_NAME), config.get(CONF_HOST), config.get(CONF_PORT),
        config.get(ATTR_ACTIVITY), harmony_conf_file, token)]
    add_devices(DEVICES, True)
    register_services(hass)
    return True


def register_services(hass):
    """Register all services for harmony devices."""
    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml'))

    hass.services.register(
        DOMAIN, SERVICE_SYNC, _sync_service, descriptions.get(SERVICE_SYNC),
        schema=HARMONY_SYNC_SCHEMA)


def _apply_service(service, service_func, *service_func_args):
    """Handle services to apply."""
    entity_ids = service.data.get('entity_id')

    if entity_ids:
        _devices = [device for device in DEVICES
                    if device.entity_id in entity_ids]
    else:
        _devices = DEVICES

    for device in _devices:
        service_func(device, *service_func_args)
        device.schedule_update_ha_state(True)


def _sync_service(service):
    _apply_service(service, HarmonyRemote.sync)


class HarmonyRemote(remote.RemoteDevice):
    """Remote representation used to control a Harmony device."""

    def __init__(self, name, host, port, activity, out_path, token):
        """Initialize HarmonyRemote class."""
        import pyharmony
        from pathlib import Path

        _LOGGER.debug("HarmonyRemote device init started for: %s", name)
        self._name = name
        self._ip = host
        self._port = port
        self._state = None
        self._current_activity = None
        self._default_activity = activity
        self._token = token
        self._config_path = out_path
        _LOGGER.debug("Retrieving harmony config using token: %s", token)
        self._config = pyharmony.ha_get_config(self._token, host, port)
        if not Path(self._config_path).is_file():
            _LOGGER.debug("Writing harmony configuration to file: %s",
                          out_path)
            pyharmony.ha_write_config_file(self._config, self._config_path)

    @property
    def name(self):
        """Return the Harmony device's name."""
        return self._name

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
        _LOGGER.debug("Polling %s for current activity", name)
        state = pyharmony.ha_get_current_activity(
            self._token, self._config, self._ip, self._port)
        _LOGGER.debug("%s current activity reported as: %s", name, state)
        self._current_activity = state
        self._state = bool(state != 'PowerOff')

    def turn_on(self, **kwargs):
        """Start an activity from the Harmony device."""
        import pyharmony
        if kwargs[ATTR_ACTIVITY]:
            activity = kwargs[ATTR_ACTIVITY]
        else:
            activity = self._default_activity

        if activity:
            pyharmony.ha_start_activity(
                self._token, self._ip, self._port, self._config, activity)
            self._state = True
        else:
            _LOGGER.error("No activity specified with turn_on service")

    def turn_off(self):
        """Start the PowerOff activity."""
        import pyharmony
        pyharmony.ha_power_off(self._token, self._ip, self._port)

    def send_command(self, **kwargs):
        """Send a set of commands to one device."""
        import pyharmony
        pyharmony.ha_send_commands(
            self._token, self._ip, self._port, kwargs[ATTR_DEVICE],
            kwargs[ATTR_COMMAND], int(kwargs[ATTR_NUM_REPEATS]),
            float(kwargs[ATTR_DELAY_SECS]))

    def sync(self):
        """Sync the Harmony device with the web service."""
        import pyharmony
        _LOGGER.debug("Syncing hub with Harmony servers")
        pyharmony.ha_sync(self._token, self._ip, self._port)
        self._config = pyharmony.ha_get_config(
            self._token, self._ip, self._port)
        _LOGGER.debug("Writing hub config to file: %s", self._config_path)
        pyharmony.ha_write_config_file(self._config, self._config_path)
