"""
Support for Tahoma devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tahoma/
"""
from collections import defaultdict
import logging
import voluptuous as vol
from requests.exceptions import RequestException

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_EXCLUDE
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import (slugify)

REQUIREMENTS = ['tahoma-api==0.0.10']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'tahoma'

TAHOMA_ID_FORMAT = '{}_{}'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_EXCLUDE, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
    }),
}, extra=vol.ALLOW_EXTRA)

TAHOMA_COMPONENTS = [
    'sensor', 'cover'
]


def setup(hass, config):
    """Activate Tahoma component."""
    from tahoma_api import TahomaApi

    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    exclude = conf.get(CONF_EXCLUDE)
    try:
        api = TahomaApi(username, password)
    except RequestException:
        _LOGGER.exception("Error communicating with Tahoma API")
        return False

    try:
        api.get_setup()
        devices = api.get_devices()
    except RequestException:
        _LOGGER.exception("Cannot fetch informations from Tahoma API")
        return False

    hass.data[DOMAIN] = {
        'controller': api,
        'devices': defaultdict(list)
    }

    for device in devices:
        _device = api.get_device(device)
        if all(ext not in _device.type for ext in exclude):
            device_type = map_tahoma_device(_device)
            if device_type is None:
                continue
            hass.data[DOMAIN]['devices'][device_type].append(_device)

    for component in TAHOMA_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


def map_tahoma_device(tahoma_device):
    """Map tahoma classes to Home Assistant types."""
    if tahoma_device.type.lower().find("shutter") != -1:
        return 'cover'
    elif tahoma_device.type == 'io:LightIOSystemSensor':
        return 'sensor'
    return None


class TahomaDevice(Entity):
    """Representation of a Tahoma device entity."""

    def __init__(self, tahoma_device, controller):
        """Initialize the device."""
        self.tahoma_device = tahoma_device
        self.controller = controller
        self._unique_id = TAHOMA_ID_FORMAT.format(
            slugify(tahoma_device.label), slugify(tahoma_device.url))
        self._name = self.tahoma_device.label

    @property
    def unique_id(self):
        """Return the unique ID for this cover."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return {'tahoma_device_id': self.tahoma_device.url}

    def apply_action(self, cmd_name, *args):
        """Apply Action to Device."""
        from tahoma_api import Action
        action = Action(self.tahoma_device.url)
        action.add_command(cmd_name, *args)
        self.controller.apply_actions('', [action])
