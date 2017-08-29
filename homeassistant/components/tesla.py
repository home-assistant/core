"""
Support for Tesla cars.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/vera/
"""
from collections import defaultdict

import voluptuous as vol

from homeassistant.util import slugify
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    ATTR_ARMED, ATTR_BATTERY_LEVEL)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['teslajsonpy==0.0.9']

DOMAIN = 'tesla'

TESLA_CONTROLLER = None

CONF_EMAIL = 'email'
CONF_PASSWORD = 'password'
CONF_UPDATE_INTERVAL = 'update_interval'

TESLA_ID_FORMAT = '{}_{}'
TESLA_DEVICES = defaultdict(list)
TESLA_ID_LIST_SCHEMA = vol.Schema([int])

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_UPDATE_INTERVAL, default=300): cv.positive_int,
    }),
}, extra=vol.ALLOW_EXTRA)

TESLA_COMPONENTS = [
    'sensor', 'lock', 'climate', 'binary_sensor', 'device_tracker'
]


def setup(hass, base_config):
    """Setup of Tesla platform."""
    global TESLA_CONTROLLER
    from teslajsonpy.controller import Controller as teslaApi

    config = base_config.get(DOMAIN)

    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)
    update_interval = config.get(CONF_UPDATE_INTERVAL)
    TESLA_CONTROLLER = teslaApi(email, password, update_interval)

    all_devices = TESLA_CONTROLLER.list_vehicles()
    if not all_devices:
        return False

    for device in all_devices:
        device_type = map_tesla_device(device)
        TESLA_DEVICES[device_type].append(device)

    for component in TESLA_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, base_config)

    return True


def map_tesla_device(tesla_device):
    """Mapping Tesla devices to array."""
    return tesla_device.hass_type


class TeslaDevice(Entity):
    """Representation of Tesla device."""

    def __init__(self, tesla_device, controller):
        """Initialisation of class."""
        self.tesla_device = tesla_device
        self.controller = controller
        self._name = self.tesla_device.name
        self.tesla_id = slugify(self.tesla_device.uniq_name)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Get polling requirement from vera device."""
        return self.tesla_device.should_poll

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}

        if self.tesla_device.has_battery():
            attr[ATTR_BATTERY_LEVEL] = \
                str(self.tesla_device.battery_level()) + '%'

        if self.tesla_device.is_armable():
            armed = self.tesla_device.is_armed()
            attr[ATTR_ARMED] = 'True' if armed else 'False'
        return attr
