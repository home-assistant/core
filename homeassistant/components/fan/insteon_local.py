"""
Support for Insteon fans via local hub control.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/fan.insteon_local/
"""
import json
import logging
import os
from datetime import timedelta

from homeassistant.components.fan import (
    ATTR_SPEED, SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH,
    SUPPORT_SET_SPEED, FanEntity)
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.util as util

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['insteon_local']
DOMAIN = 'fan'

INSTEON_LOCAL_FANS_CONF = 'insteon_local_fans.conf'

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

SUPPORT_INSTEON_LOCAL = SUPPORT_SET_SPEED


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Insteon local fan platform."""
    insteonhub = hass.data['insteon_local']

    conf_fans = config_from_file(hass.config.path(INSTEON_LOCAL_FANS_CONF))
    if conf_fans:
        for device_id in conf_fans:
            setup_fan(device_id, conf_fans[device_id], insteonhub, hass,
                      add_devices)

    else:
        linked = insteonhub.get_linked()

        for device_id in linked:
            if (linked[device_id]['cat_type'] == 'dimmer' and
                    linked[device_id]['sku'] == '2475F' and
                    device_id not in conf_fans):
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

    def insteon_fan_config_callback(data):
        """The actions to do when our configuration callback is called."""
        setup_fan(device_id, data.get('name'), insteonhub, hass,
                  add_devices_callback)

    _CONFIGURING[device_id] = configurator.request_config(
        'Insteon  ' + model + ' addr: ' + device_id,
        insteon_fan_config_callback,
        description=('Enter a name for ' + model + ' Fan addr: ' + device_id),
        entity_picture='/static/images/config_insteon.png',
        submit_caption='Confirm',
        fields=[{'id': 'name', 'name': 'Name', 'type': ''}]
    )


def setup_fan(device_id, name, insteonhub, hass, add_devices_callback):
    """Set up the fan."""
    if device_id in _CONFIGURING:
        request_id = _CONFIGURING.pop(device_id)
        configurator = hass.components.configurator
        configurator.request_done(request_id)
        _LOGGER.info("Device configuration done!")

    conf_fans = config_from_file(hass.config.path(INSTEON_LOCAL_FANS_CONF))
    if device_id not in conf_fans:
        conf_fans[device_id] = name

    if not config_from_file(
            hass.config.path(INSTEON_LOCAL_FANS_CONF),
            conf_fans):
        _LOGGER.error("Failed to save configuration file")

    device = insteonhub.fan(device_id)
    add_devices_callback([InsteonLocalFanDevice(device, name)])


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
                _LOGGER.error("Reading configuration file failed: %s", error)
                # This won't work yet
                return False
        else:
            return {}


class InsteonLocalFanDevice(FanEntity):
    """An abstract Class for an Insteon node."""

    def __init__(self, node, name):
        """Initialize the device."""
        self.node = node
        self.node.deviceName = name
        self._speed = SPEED_OFF

    @property
    def name(self):
        """Return the name of the node."""
        return self.node.deviceName

    @property
    def unique_id(self):
        """Return the ID of this Insteon node."""
        return 'insteon_local_{}_fan'.format(self.node.device_id)

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return self._speed

    @property
    def speed_list(self: ToggleEntity) -> list:
        """Get the list of available speeds."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Update state of the fan."""
        resp = self.node.status()
        if 'cmd2' in resp:
            if resp['cmd2'] == '00':
                self._speed = SPEED_OFF
            elif resp['cmd2'] == '55':
                self._speed = SPEED_LOW
            elif resp['cmd2'] == 'AA':
                self._speed = SPEED_MEDIUM
            elif resp['cmd2'] == 'FF':
                self._speed = SPEED_HIGH

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_INSTEON_LOCAL

    def turn_on(self: ToggleEntity, speed: str=None, **kwargs) -> None:
        """Turn device on."""
        if speed is None:
            if ATTR_SPEED in kwargs:
                speed = kwargs[ATTR_SPEED]
            else:
                speed = SPEED_MEDIUM

        self.set_speed(speed)

    def turn_off(self: ToggleEntity, **kwargs) -> None:
        """Turn device off."""
        self.node.off()

    def set_speed(self: ToggleEntity, speed: str) -> None:
        """Set the speed of the fan."""
        if self.node.on(speed):
            self._speed = speed
