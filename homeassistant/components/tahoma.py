"""
Support for Tahoma devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tahoma/
"""
import logging
import voluptuous as vol

from collections import defaultdict
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_EXCLUDE
from homeassistant.components.tahoma_api import (TahomaApi)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import (slugify)

TAHOMA_CONTROLLER = None

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'tahoma'

TAHOMA_ID_LIST_SCHEMA = vol.Schema([cv.string])

TAHOMA_DEVICES = defaultdict(list)
TAHOMA_ID_FORMAT = '{}_{}'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_EXCLUDE, default=[]): TAHOMA_ID_LIST_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Activate Tahoma component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    exclude = conf.get(CONF_EXCLUDE)
    try:
        TAHOMA_CONTROLLER = TahomaApi(username, password)
    except Exception:
        _LOGGER.exception("Error communicating with Tahoma API")
        return False

    hass.data['TAHOMA_CONTROLLER'] = TAHOMA_CONTROLLER

    TAHOMA_DEVICES['api'] = TAHOMA_CONTROLLER
    try:
        TAHOMA_CONTROLLER.getSetup()
        devices = TAHOMA_CONTROLLER.getDevices()
    except Exception:
        _LOGGER.exception("Cannot feht informations from Tahoma API")
        return False

    for device in devices:
        d = TAHOMA_CONTROLLER.getDevice(device)
        _LOGGER.error(d.label)
        _LOGGER.error(d.type)
        if any(ext not in d.type for ext in exclude):
            device_type = map_tahoma_device(d)
            if device_type is None:
                continue
            TAHOMA_DEVICES[device_type].append(d)

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
        # Append device id to prevent name clashes in HA.
        # self.tahoma_id = tahoma_device.url
        self.tahoma_id = TAHOMA_ID_FORMAT.format(
            slugify(tahoma_device.label), slugify(tahoma_device.url))
        self._name = self.tahoma_device.label

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Get polling requirement from tahoma device."""
        return True

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        attr['Tahoma Device Id'] = self.tahoma_device.url

        return attr
