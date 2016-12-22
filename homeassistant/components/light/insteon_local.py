"""
Support for Insteon dimmers via local hub control.

Based on the insteonlocal library
https://github.com/phareous/insteonlocal

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.insteon_local/

--
Example platform config
--

insteon_local:
  host: YOUR HUB IP
  username: YOUR HUB USERNAME
  password: YOUR HUB PASSWORD
  timeout: 10
  port: 25105

"""
import json
import logging
import os
from time import sleep
from datetime import timedelta
from homeassistant.components.light import (ATTR_BRIGHTNESS,
                                            SUPPORT_BRIGHTNESS, Light)
from homeassistant.loader import get_component
import homeassistant.util as util

INSTEON_LOCAL_LIGHTS_CONF = 'insteon_local_lights.conf'

DEPENDENCIES = ['insteon_local']

SUPPORT_INSTEON_LOCAL = SUPPORT_BRIGHTNESS

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

DOMAIN = "light"

_LOGGER = logging.getLogger(__name__)
_CONFIGURING = {}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Insteon local light platform."""
    insteonhub = hass.data['insteon_local']

    conf_lights = config_from_file(hass.config.path(INSTEON_LOCAL_LIGHTS_CONF))
    if len(conf_lights):
        for device_id in conf_lights:
            setup_light(device_id, conf_lights[device_id], insteonhub, hass,
                        add_devices)

    linked = insteonhub.getLinked()

    for id in linked:
        if linked[id]['cat_type'] == 'dimmer' and id not in conf_lights:
            request_configuration(id, insteonhub, linked[id]['model_name'],
                                  hass, add_devices)


def request_configuration(id, insteonhub, model, hass, add_devices_callback):
    """Request configuration steps from the user."""
    configurator = get_component('configurator')

    # We got an error if this method is called while we are configuring
    if id in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[id], 'Failed to register, please try again.')

        return

    def insteon_light_configuration_callback(data):
        """The actions to do when our configuration callback is called."""
        setup_light(id, data.get('name'), insteonhub, hass,
                    add_devices_callback)

    _CONFIGURING[id] = configurator.request_config(
        hass, 'Insteon  ' + model + ' ' + id,
        insteon_light_configuration_callback,
        description=('Enter a name for ' + model + ' ' + id),
        entity_picture='/static/images/config_insteon.png',
        submit_caption='Confirm',
        fields=[{'id': 'name', 'name': 'Name', 'type': ''}]
    )


def setup_light(id, name, insteonhub, hass, add_devices_callback):
    """Setup light."""
    if id in _CONFIGURING:
        request_id = _CONFIGURING.pop(id)
        configurator = get_component('configurator')
        configurator.request_done(request_id)
        _LOGGER.info('Device configuration done!')

    conf_lights = config_from_file(hass.config.path(INSTEON_LOCAL_LIGHTS_CONF))
    if id not in conf_lights:
        conf_lights[id] = name

    if not config_from_file(
            hass.config.path(INSTEON_LOCAL_LIGHTS_CONF),
            conf_lights):
        _LOGGER.error('failed to save config file')

    device = insteonhub.dimmer(id)
    add_devices_callback([InsteonLocalDimmerDevice(device, name)])


def config_from_file(filename, config=None):
    """Small configuration file management function."""
    if config:
        # We're writing configuration
        try:
            with open(filename, 'w') as fdesc:
                fdesc.write(json.dumps(config))
        except IOError as error:
            _LOGGER.error('Saving config file failed: %s', error)
            return False
        return True
    else:
        # We're reading config
        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as fdesc:
                    return json.loads(fdesc.read())
            except IOError as error:
                _LOGGER.error('Reading config file failed: %s', error)
                # This won't work yet
                return False
        else:
            return {}


class InsteonLocalDimmerDevice(Light):
    """An abstract Class for an Insteon node."""

    def __init__(self, node, name):
        """Initialize the device."""
        self.node = node
        self.node.deviceName = name
        self._value = 0

    @property
    def name(self):
        """Return the the name of the node."""
        return self.node.deviceName

    @property
    def unique_id(self):
        """Return the ID of this insteon node."""
        return 'insteon_local_' + self.node.deviceId

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._value

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Update state of the sensor."""
        devid = self.node.deviceId.upper()
        self.node.hub.directCommand(devid, '19', '00')
        resp = self.node.hub.getBufferStatus(devid)
        attempts = 1
        while 'cmd2' not in resp and attempts < 9:
            if attempts % 3 == 0:
                self.node.hub.directCommand(devid, '19', '00')
            else:
                sleep(1)
            resp = self.node.hub.getBufferStatus(devid)
            attempts += 1

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

        self.node.on(brightness)

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.node.off()
