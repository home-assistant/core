"""
Support for TCP Connected (Greenwave Reality) lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.tcpbulbs/
"""

import logging
import voluptuous as vol
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, Light, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS)
from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv
SUPPORTED_FEATURES = (SUPPORT_BRIGHTNESS)
REQUIREMENTS = ['xmltodict==0.11.0']
_LOGGER = logging.getLogger(__name__)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
})


def pull_xml(host):
    """Pull XML Data from Gateway."""
    import xmltodict
    resp = gateway_action(host, 0, 'xml', 0)
    return xmltodict.parse(resp.content)


def number_range(value, left_min, left_max, right_min, right_max):
    """Map one number range to another."""
    # Figure out how 'wide' each range is
    left_span = left_max - left_min
    right_span = right_max - right_min

    # Convert the left range into a 0-1 range (float)
    value_scaled = float(value - left_min) / float(left_span)

    # Convert the 0-1 range into a value in the right range.
    return int(right_min + (value_scaled * right_span))


def get_brightness(device):
    """Get Brightness of Device."""
    if 'level' in device:
        level = number_range(int(device['level']), 1, 100, 1, 255)
        return level
    else:
        return 0


def is_online(device):
    """Check Device Status."""
    return 'offline' not in device


def gateway_action(host, did, action, value):
    """Do Action for TCP Connected Gateway."""
    import requests
    if action == 'xml':
        url = ('http://' + host + '/gwr/gop.php?cmd=GWRBatch&data=<gwrcmds>'
               '<gwrcmd><gcmd>RoomGetCarousel</gcmd><gdata><gip><version>1'
               '</version><token>1234567890</token><fields>name,status'
               '</fields></gip></gdata></gwrcmd></gwrcmds>&fmt=xml')
        resp = requests.get(url)
        return resp
    if action == 'level':
        action = '<type>level</type>'
    else:
        action = ''
    url = ('http://' + host + '/gwr/gop.php?cmd=DeviceSendCommand&data=<gip>'
           '<version>1</version><token>1234567890</token>'
           '<did>' + did + '</did>'
           '<value>' + str(value) + '</value>' + action + '</gip>&fmt=xml')
    requests.get(url)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup TCP Connected Platform."""
    host = config.get(CONF_HOST)
    doc = pull_xml(host)
    add_devices(TcpLights(device, host) for device in
                doc['gwrcmds']['gwrcmd']['gdata']['gip']['room']['device'])


class TcpLights(Light):
    """Representation of an TCP Connected Light."""

    def __init__(self, light, host):
        """Initialize a TCP Connected Light."""
        self._did = light['did']
        self._name = light['name']
        self._state = int(light['state'])
        self._brightness = get_brightness(light)
        self._host = host
        self._online = is_online(light)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES

    @property
    def available(self):
        """Return True if entity is available."""
        return self._online

    @property
    def did(self):
        """Return the device id of this light."""
        return self._did

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        temp_brightness = str(number_range(kwargs.get(ATTR_BRIGHTNESS, 255),
                                           1, 255, 1, 100))
        gateway_action(self._host, self._did, 'level', temp_brightness)
        gateway_action(self._host, self._did, 'on', 1)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        gateway_action(self._host, self._did, 'off', 0)

    def update(self):
        """Fetch new state data for this light."""
        doc = pull_xml(self._host)

        for device in \
                doc['gwrcmds']['gwrcmd']['gdata']['gip']['room']['device']:
            if device['did'] == self._did:
                self._state = int(device['state'])
                self._brightness = get_brightness(device)
                self._online = is_online(device)
                self._name = device['name']
