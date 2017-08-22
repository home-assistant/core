"""
This component provides basic support for Abode Home Security system.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/abode/
"""
import logging

import voluptuous as vol
from requests.exceptions import HTTPError, ConnectTimeout
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.const import (ATTR_ATTRIBUTION,
    CONF_USERNAME, CONF_PASSWORD, CONF_NAME, EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = ['abodepy==0.7.2']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by goabode.com"

DOMAIN = 'abode'
DEFAULT_NAME = 'Abode'
DEFAULT_ENTITY_NAMESPACE = 'abode'

ABODE_CONTROLLER = None

NOTIFICATION_ID = 'abode_notification'
NOTIFICATION_TITLE = 'Abode Security Setup'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

def setup(hass, config):
    """Set up Abode component."""
    global ABODE_CONTROLLER
    import abodepy

    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    try:
        ABODE_CONTROLLER = abodepy.Abode(username, password)
        hass.data[DOMAIN] = ABODE_CONTROLLER

        devices = ABODE_CONTROLLER.get_devices()

        _LOGGER.info("Logged in to Abode and found %s devices",
                     len(devices))

        for component in ['binary_sensor', 'alarm_control_panel', 'lock']:
            discovery.load_platform(hass, component, DOMAIN, {}, config)

        def logout(event):
            """Logout of Abode."""
            ABODE_CONTROLLER.stop_listener()
            ABODE_CONTROLLER.logout()
            _LOGGER.info("Logged out of Abode")

        hass.bus.listen(EVENT_HOMEASSISTANT_STOP, logout)

        ABODE_CONTROLLER.start_listener()

    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Abode: %s", str(ex))
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    return True


class AbodeDevice(Entity):
    """Representation of an Abode device."""

    def __init__(self, hass, controller, device):
        """Initialize a sensor for Abode device."""
        self._controller = controller
        self._device = device
        self._name = "{0} {1}".format(self._device.type, self._device.name)
        self._attrs = None

        self._controller.register(self._device, self._update_callback)

        _LOGGER.info("Device initialized: %s", self.name)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        self._attrs = {}
        self._attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        self._attrs['device_id'] = self._device.device_id
        self._attrs['battery_low'] = self._device.battery_low

        return self._attrs

    def _update_callback(self, device):
        """Update the device state."""
        _LOGGER.info("Device update received: %s", self.name)
        self._device = device
        self.schedule_update_ha_state()
