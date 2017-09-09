"""
This component provides basic support for Abode Home Security system.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/abode/
"""
import asyncio
import logging

import voluptuous as vol
from requests.exceptions import HTTPError, ConnectTimeout
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.const import (ATTR_ATTRIBUTION,
                                 CONF_USERNAME, CONF_PASSWORD,
                                 CONF_NAME, EVENT_HOMEASSISTANT_STOP,
                                 EVENT_HOMEASSISTANT_START)

REQUIREMENTS = ['abodepy==0.9.0']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by goabode.com"

DOMAIN = 'abode'
DEFAULT_NAME = 'Abode'
DATA_ABODE = 'abode'

NOTIFICATION_ID = 'abode_notification'
NOTIFICATION_TITLE = 'Abode Security Setup'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

ABODE_PLATFORMS = [
    'alarm_control_panel', 'binary_sensor', 'lock', 'switch', 'cover'
]


def setup(hass, config):
    """Set up Abode component."""
    import abodepy

    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    try:
        hass.data[DATA_ABODE] = abode = abodepy.Abode(
            username, password, auto_login=True, get_devices=True)

    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Abode: %s", str(ex))
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    for platform in ABODE_PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    def logout(event):
        """Logout of Abode."""
        abode.stop_listener()
        abode.logout()
        _LOGGER.info("Logged out of Abode")

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, logout)

    def startup(event):
        """Listen for push events."""
        abode.start_listener()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, startup)

    return True


class AbodeDevice(Entity):
    """Representation of an Abode device."""

    def __init__(self, controller, device):
        """Initialize a sensor for Abode device."""
        self._controller = controller
        self._device = device

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe Abode events."""
        self.hass.async_add_job(
            self._controller.register, self._device,
            self._update_callback
        )

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._device.name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            'device_id': self._device.device_id,
            'battery_low': self._device.battery_low,
            'no_response': self._device.no_response
        }

    def _update_callback(self, device):
        """Update the device state."""
        self.schedule_update_ha_state()
