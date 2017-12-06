"""
Support for Insteon dimmers via local hub control.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.insteon_local/
"""
import logging
from datetime import timedelta

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
import homeassistant.util as util
from homeassistant.util.json import load_json, save_json


_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['insteon_local']
DOMAIN = 'light'

INSTEON_LOCAL_LIGHTS_CONF = 'insteon_local_lights.conf'

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

SUPPORT_INSTEON_LOCAL = SUPPORT_BRIGHTNESS


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Insteon local light platform."""
    insteonhub = hass.data['insteon_local']

    conf_lights = load_json(hass.config.path(INSTEON_LOCAL_LIGHTS_CONF))
    if conf_lights:
        for device_id in conf_lights:
            setup_light(device_id, conf_lights[device_id], insteonhub, hass,
                        add_devices)

    else:
        linked = insteonhub.get_linked()

        for device_id in linked:
            if (linked[device_id]['cat_type'] == 'dimmer' and
                    device_id not in conf_lights):
                request_configuration(device_id,
                                      insteonhub,
                                      linked[device_id]['model_name'] + ' ' +
                                      linked[device_id]['sku'],
                                      hass, add_devices)


def request_configuration(device_id, insteonhub, model, hass,
                          add_devices_callback):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator

    # We got an error if this method is called while we are configuring
    if device_id in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[device_id], 'Failed to register, please try again.')

        return

    def insteon_light_config_callback(data):
        """Set up actions to do when our configuration callback is called."""
        setup_light(device_id, data.get('name'), insteonhub, hass,
                    add_devices_callback)

    _CONFIGURING[device_id] = configurator.request_config(
        'Insteon  ' + model + ' addr: ' + device_id,
        insteon_light_config_callback,
        description=('Enter a name for ' + model + ' addr: ' + device_id),
        entity_picture='/static/images/config_insteon.png',
        submit_caption='Confirm',
        fields=[{'id': 'name', 'name': 'Name', 'type': ''}]
    )


def setup_light(device_id, name, insteonhub, hass, add_devices_callback):
    """Set up the light."""
    if device_id in _CONFIGURING:
        request_id = _CONFIGURING.pop(device_id)
        configurator = hass.components.configurator
        configurator.request_done(request_id)
        _LOGGER.debug("Device configuration done")

    conf_lights = load_json(hass.config.path(INSTEON_LOCAL_LIGHTS_CONF))
    if device_id not in conf_lights:
        conf_lights[device_id] = name

    save_json(hass.config.path(INSTEON_LOCAL_LIGHTS_CONF), conf_lights)

    device = insteonhub.dimmer(device_id)
    add_devices_callback([InsteonLocalDimmerDevice(device, name)])


class InsteonLocalDimmerDevice(Light):
    """An abstract Class for an Insteon node."""

    def __init__(self, node, name):
        """Initialize the device."""
        self.node = node
        self.node.deviceName = name
        self._value = 0

    @property
    def name(self):
        """Return the name of the node."""
        return self.node.deviceName

    @property
    def unique_id(self):
        """Return the ID of this Insteon node."""
        return 'insteon_local_{}'.format(self.node.device_id)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._value

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Update state of the light."""
        resp = self.node.status(0)

        while 'error' in resp and resp['error'] is True:
            resp = self.node.status(0)

        if 'cmd2' in resp:
            self._value = int(resp['cmd2'], 16)

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return self._value != 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_INSTEON_LOCAL

    def turn_on(self, **kwargs):
        """Turn device on."""
        brightness = 100
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS]) / 255 * 100

        self.node.change_level(brightness)

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.node.off()
