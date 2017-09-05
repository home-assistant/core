"""
Support for FRITZ!Box call forwarding on/off.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.fritzbox_callforwarding/
"""

import logging
from datetime import timedelta
import voluptuous as vol
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['fritzconnection==0.6.5']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = '169.254.1.1'  # IP valid for all Fritz!Box routers
DEFAULT_PORT = 49000
DEFAULT_USERNAME = 'admin'
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=60)
ICON = 'mdi:phone-forward'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_PASSWORD, default=''): cv.string,
     vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
     vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
     vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string})


class FritzCallForwardingSwitch(SwitchDevice):
    """Representation of a FRITZ!CallForwarding switch."""

    def __init__(self, fritz_box, call_forwarding_dict):
        """Initialize the switch with a call forwarding dict."""
        self.fritz_box = fritz_box
        self._name = "callforwarding_" + call_forwarding_dict['uid']
        self.uid = call_forwarding_dict['uid']
        self.from_number = call_forwarding_dict['from_number']
        self.to_number = call_forwarding_dict['to_number']
        self.connection_type = call_forwarding_dict['connection_type']
        self.enabled = call_forwarding_dict['enabled']

    @property
    def name(self):
        """Return the name of the FRITZ!CallForwarding switch, if any."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def is_on(self):
        """Return true if switch is on."""
        return bool(self.enabled)

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.enabled = self.fritz_box.set_call_forwarding(self.uid, 1)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.enabled = self.fritz_box.set_call_forwarding(self.uid, 0)

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def update(self):
        """Get the latest call forwarding data.

        from the fritz box and updates the states accordingly.
        """
        self.enabled = self.fritz_box.get_call_forwarding_status_by_uid(
            self.uid)

    def __str__(self):
        """Create a string representation of a FritzCallForwardingSwitch."""
        return "%s --> %s: %s" % (self.from_number,
                                  self.to_number, self.enabled)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the fritzbox connection."""
    # pylint: disable=import-error
    from fritzconnection import FritzCallforwarding
    from fritzconnection.fritzconnection import FritzConnectionException

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    fritz_box = None

    try:
        fritz_box = FritzCallforwarding(address=host,
                                        port=port,
                                        user=username,
                                        password=password)
    except (ValueError, TypeError, FritzConnectionException):
        fritz_box = None

    if fritz_box is None:
        _LOGGER.error('Failed to establish connection to FRITZ!Box '
                      'with IP: %s', host)
        raise ConnectionError('Failed to establish connection to FRITZ!Box '
                              'with IP: %s', host)
    else:
        _LOGGER.debug('Successfully connected to FRITZ!Box')

    devices = []
    for call_forwarding in fritz_box.get_call_forwardings():
        devices.append(FritzCallForwardingSwitch(fritz_box, call_forwarding))
    add_devices(devices)
