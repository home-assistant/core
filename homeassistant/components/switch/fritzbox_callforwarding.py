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

REQUIREMENTS = ['fritzconnection==0.6.3']

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


class CallForwarding:
    """Representation of call forwarding entity."""

    def __init__(self, fritz_box, uid, from_number,
                 to_number, connection_type, enabled):
        """Initialize the call forwarding entity."""
        self.fritz_box = fritz_box
        self.name = "callforwarding_" + uid
        self.uid = uid
        self.from_number = from_number
        self.to_number = to_number
        self.connection_type = connection_type
        self.enabled = enabled

    def enable(self):
        """Enable the call forwarding for a uid."""
        kwargs = {'NewDeflectionId': self.uid, 'NewEnable': 1}
        self.fritz_box.call_action(
            'X_AVM-DE_OnTel:1', 'SetDeflectionEnable', **kwargs)
        self.enabled = 1

    def disable(self):
        """Disable the call forwarding for a uid."""
        kwargs = {'NewDeflectionId': self.uid, 'NewEnable': 0}

        self.fritz_box.call_action(
            'X_AVM-DE_OnTel:1', 'SetDeflectionEnable', **kwargs)
        self.enabled = 0

    def __str__(self):
        """Create a string representation of a CallForwarding."""
        return "%s --> %s: %s" % (self.from_number,
                                  self.to_number, self.enabled)


class FritzCallForwardingSwitch(SwitchDevice):
    """Representation of a FRITZ!CallForwarding switch."""

    def __init__(self, call_forwarding):
        """Initialize the switch with a call forwarding from the fritzbox."""
        self._call_forwarding = call_forwarding

    @property
    def name(self):
        """Return the name of the FRITZ!CallForwarding switch, if any."""
        return self._call_forwarding.name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def is_on(self):
        """Return true if switch is on."""
        return bool(self._call_forwarding.enabled)

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._call_forwarding.enable()

    def turn_off(self):
        """Turn the switch off."""
        self._call_forwarding.disable()

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def update(self):
        """Get the latest call forwarding data.

        from the fritz box and updates the states.
        """
        self._call_forwarding = get_call_forwarding_by_uid(
            self._call_forwarding.fritz_box, self._call_forwarding.uid)
        _LOGGER.debug(self._call_forwarding)

    def __str__(self):
        """Create a string representation of a FritzCallForwardingSwitch."""
        return str(self._call_forwarding)


def get_call_forwardings(fritz_box):
    """Get a list with all CallForwarding Objects ."""
    import xml.etree.ElementTree as ET

    call_forwardings = []
    deflections = fritz_box.call_action('X_AVM-DE_OnTel:1', 'GetDeflections')
    deflection_list = ET.fromstring(deflections['NewDeflectionList'])

    for deflection in deflection_list.findall('Item'):
        uid = deflection.find('DeflectionId').text
        enabled = int(deflection.find('Enable').text)
        connection_type = deflection.find('Type').text
        from_number = deflection.find('Number').text
        to_number = deflection.find('DeflectionToNumber').text
        if to_number is not None:  # Filter out blocked numbers for now

            call_forwardings.append(CallForwarding(fritz_box,
                                                   uid,
                                                   from_number,
                                                   to_number,
                                                   connection_type,
                                                   enabled))

    return call_forwardings


def get_call_forwarding_by_uid(fritz_box, uid):
    """Get a CallForwarding Object for a uid ."""
    kwargs = {'NewDeflectionId': uid}
    deflection_dict = fritz_box.call_action(
        'X_AVM-DE_OnTel:1', 'GetDeflection', **kwargs)

    return CallForwarding(fritz_box,
                          uid,
                          deflection_dict['NewNumber'],
                          deflection_dict['NewDeflectionToNumber'],
                          deflection_dict['NewType'],
                          int(deflection_dict['NewEnable']))


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the fritzbox connection."""
    from fritzconnection import FritzConnection
    from fritzconnection.fritzconnection import FritzConnectionException

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    fritz_box = None

    try:
        fritz_box = FritzConnection(
            address=host, port=port, user=username, password=password)
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
    for call_forwarding in get_call_forwardings(fritz_box):
        devices.append(FritzCallForwardingSwitch(call_forwarding))
    add_devices(devices)
