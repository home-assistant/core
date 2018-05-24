"""
Support for 1-Wire environment switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.onewire/
"""
import os
import logging
from glob import glob

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchDevice
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.const import DEVICE_DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

CONF_MOUNT_DIR = 'mount_dir'
CONF_NAMES = 'names'

DEFAULT_MOUNT_DIR = '/sys/bus/w1/devices/'
DEVICE_SWITCHES = {'05': {'A': 'PIO'},
                   '12': {'A': 'PIO.A',
                          'B': 'PIO.B'},
                   '29': {'0': 'PIO.0',
                          '1': 'PIO.1',
                          '2': 'PIO.2',
                          '3': 'PIO.3',
                          '4': 'PIO.4',
                          '5': 'PIO.5',
                          '6': 'PIO.6',
                          '7': 'PIO.7'},
                   '3A': {'A': 'PIO.A',
                          'B': 'PIO.B'}}

DEVICE_SWITCH_ON = "1"
DEVICE_SWITCH_OFF = "0"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAMES): {cv.string: cv.string},
    vol.Optional(CONF_MOUNT_DIR, default=DEFAULT_MOUNT_DIR): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the one wire Switches."""
    base_dir = config.get(CONF_MOUNT_DIR)
    devs = []
    device_names = {}
    if 'names' in config:
        if isinstance(config['names'], dict):
            device_names = config['names']

    for family_file_path in glob(os.path.join(base_dir, '*', 'family')):
        with open(family_file_path, "r") as family_file:
            family = family_file.read()
        if family in DEVICE_SWITCHES:
            switch_id = os.path.split(
                os.path.split(family_file_path)[0])[1]
            for switch_key, switch_value in DEVICE_SWITCHES[family].items():
                switch_id_complete = switch_id + "_" + switch_key
                device_file = os.path.join(
                    os.path.split(family_file_path)[0], switch_value)
                devs.append(OneWireSwitch(device_names.get(switch_id_complete,
                                                           switch_id_complete),
                                          device_file))

    if devs == []:
        _LOGGER.error("No onewire sensor found. Check if dtoverlay=w1-gpio "
                      "is in your /boot/config.txt. "
                      "Check the mount_dir parameter if it's defined")
        return

    add_devices(devs, True)


class OneWireSwitch(SwitchDevice):
    """Representation of a OneWire switch."""

    def __init__(self, name, device_file):
        """Initialize the OneWire switch."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._device_file = device_file
        self._state = None

    def _read_value_raw(self):
        """Read the value as it is returned by the switch."""
        try:
            with open(self._device_file, 'r') as ds_device_file:
                content = ds_device_file.read()
        except FileNotFoundError:
            msg = "1Wire switch file not found: %s", self._device_file
            _LOGGER.warning(msg)
        except OSError:
            _LOGGER.warning("Error reading switch file %s", self._device_file)
        return content

    def _write_value_raw(self, value):
        """Write the value to the switch."""
        if value not in [DEVICE_SWITCH_ON,DEVICE_SWITCH_OFF]:
            _LOGGER.error("Error in setting wrong value %s", value)
            return False
        else:
            try:
                with open(self._device_file, 'w') as ds_device_file:
                    ds_device_file.write(value)
                return True
            except FileNotFoundError:
                msg = "1Wire switch file not found: %s", self._device_file
                _LOGGER.warning(msg)
            except OSError:
                msg = "Error writing switch file %s", self._device_file
                _LOGGER.warning(msg)
            return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def update(self):
        self._state = self._read_value_raw() == DEVICE_SWITCH_ON
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self._write_value_raw(self, DEVICE_SWITCH_ON):
            self._state = True
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self._write_value_raw(self, DEVICE_SWITCH_OFF):
            self._state = False
            self.schedule_update_ha_state()
