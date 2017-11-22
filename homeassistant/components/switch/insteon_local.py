"""
Support for Insteon switch devices via local hub support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.insteon_local/
"""
import logging
from datetime import timedelta

from homeassistant.components.switch import SwitchDevice
import homeassistant.util as util
from homeassistant.util.json import load_json, save_json

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['insteon_local']
DOMAIN = 'switch'

INSTEON_LOCAL_SWITCH_CONF = 'insteon_local_switch.conf'

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Insteon local switch platform."""
    insteonhub = hass.data['insteon_local']

    conf_switches = load_json(hass.config.path(INSTEON_LOCAL_SWITCH_CONF))
    if conf_switches:
        for device_id in conf_switches:
            setup_switch(
                device_id, conf_switches[device_id], insteonhub, hass,
                add_devices)
    else:
        linked = insteonhub.get_linked()

        for device_id in linked:
            if linked[device_id]['cat_type'] == 'switch'\
                    and device_id not in conf_switches:
                request_configuration(device_id, insteonhub,
                                      linked[device_id]['model_name'] + ' ' +
                                      linked[device_id]['sku'],
                                      hass, add_devices)


def request_configuration(
        device_id, insteonhub, model, hass, add_devices_callback):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator

    # We got an error if this method is called while we are configuring
    if device_id in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[device_id], 'Failed to register, please try again.')

        return

    def insteon_switch_config_callback(data):
        """Handle configuration changes."""
        setup_switch(device_id, data.get('name'), insteonhub, hass,
                     add_devices_callback)

    _CONFIGURING[device_id] = configurator.request_config(
        'Insteon Switch ' + model + ' addr: ' + device_id,
        insteon_switch_config_callback,
        description=('Enter a name for ' + model + ' addr: ' + device_id),
        entity_picture='/static/images/config_insteon.png',
        submit_caption='Confirm',
        fields=[{'id': 'name', 'name': 'Name', 'type': ''}]
    )


def setup_switch(device_id, name, insteonhub, hass, add_devices_callback):
    """Set up the switch."""
    if device_id in _CONFIGURING:
        request_id = _CONFIGURING.pop(device_id)
        configurator = hass.components.configurator
        configurator.request_done(request_id)
        _LOGGER.info("Device configuration done")

    conf_switch = load_json(hass.config.path(INSTEON_LOCAL_SWITCH_CONF))
    if device_id not in conf_switch:
        conf_switch[device_id] = name

    save_json(hass.config.path(INSTEON_LOCAL_SWITCH_CONF), conf_switch)

    device = insteonhub.switch(device_id)
    add_devices_callback([InsteonLocalSwitchDevice(device, name)])


class InsteonLocalSwitchDevice(SwitchDevice):
    """An abstract Class for an Insteon node."""

    def __init__(self, node, name):
        """Initialize the device."""
        self.node = node
        self.node.deviceName = name
        self._state = False

    @property
    def name(self):
        """Return the name of the node."""
        return self.node.deviceName

    @property
    def unique_id(self):
        """Return the ID of this Insteon node."""
        return 'insteon_local_{}'.format(self.node.device_id)

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Get the updated status of the switch."""
        resp = self.node.status(0)

        while 'error' in resp and resp['error'] is True:
            resp = self.node.status(0)

        if 'cmd2' in resp:
            self._state = int(resp['cmd2'], 16) > 0

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.node.on()
        self._state = True

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.node.off()
        self._state = False
