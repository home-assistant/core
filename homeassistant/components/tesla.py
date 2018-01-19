"""
Support for Tesla cars.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tesla/
"""
from collections import defaultdict
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_BATTERY_LEVEL, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

REQUIREMENTS = ['teslajsonpy==0.0.19']

DOMAIN = 'tesla'

_LOGGER = logging.getLogger(__name__)

TESLA_ID_FORMAT = '{}_{}'
TESLA_ID_LIST_SCHEMA = vol.Schema([int])

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=300):
            vol.All(cv.positive_int, vol.Clamp(min=300)),
    }),
}, extra=vol.ALLOW_EXTRA)

NOTIFICATION_ID = 'tesla_integration_notification'
NOTIFICATION_TITLE = 'Tesla integration setup'

TESLA_COMPONENTS = [
    'sensor', 'lock', 'climate', 'binary_sensor', 'device_tracker', 'switch'
]


def setup(hass, base_config):
    """Set up of Tesla component."""
    from teslajsonpy import Controller as teslaAPI, TeslaException

    config = base_config.get(DOMAIN)

    email = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    update_interval = config.get(CONF_SCAN_INTERVAL)
    if hass.data.get(DOMAIN) is None:
        try:
            hass.data[DOMAIN] = {
                'controller': teslaAPI(email, password, update_interval),
                'devices': defaultdict(list)
            }
            _LOGGER.debug("Connected to the Tesla API.")
        except TeslaException as ex:
            if ex.code == 401:
                hass.components.persistent_notification.create(
                    "Error:<br />Please check username and password."
                    "You will need to restart Home Assistant after fixing.",
                    title=NOTIFICATION_TITLE,
                    notification_id=NOTIFICATION_ID)
            else:
                hass.components.persistent_notification.create(
                    "Error:<br />Can't communicate with Tesla API.<br />"
                    "Error code: {} Reason: {}"
                    "You will need to restart Home Assistant after fixing."
                    "".format(ex.code, ex.message),
                    title=NOTIFICATION_TITLE,
                    notification_id=NOTIFICATION_ID)
            _LOGGER.error("Unable to communicate with Tesla API: %s",
                          ex.message)
            return False

    all_devices = hass.data[DOMAIN]['controller'].list_vehicles()

    if not all_devices:
        return False

    for device in all_devices:
        hass.data[DOMAIN]['devices'][device.hass_type].append(device)

    for component in TESLA_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, base_config)

    return True


class TeslaDevice(Entity):
    """Representation of a Tesla device."""

    def __init__(self, tesla_device, controller):
        """Initialise of the Tesla device."""
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
        """Return the polling state."""
        return self.tesla_device.should_poll

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}

        if self.tesla_device.has_battery():
            attr[ATTR_BATTERY_LEVEL] = self.tesla_device.battery_level()
        return attr
