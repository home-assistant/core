# -*- coding: utf-8 -*-
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import STATE_ON, STATE_OFF, DEVICE_DEFAULT_NAME
import subprocess
import os


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return 433Mhz switches. """

    device_data = config.get('device_data', {})
    devices = []

    for k, v in device_data.items():
        devices.append(
            Switch443(
                k,
                # pad with 0s
                (('0'*5) + str(v.get('group', '')))[-5:],
                int(v.get('device', '1'))))

    add_devices_callback(devices)


class Switch443(ToggleEntity):
    def __init__(self, name, group, device):
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = STATE_OFF
        self._group = group
        self._device = device

    @staticmethod
    def _switch(system_code, unit_code, command):
        assert (subprocess.call(['sudo',
                                 os.path.join(os.path.dirname(__file__),
                                              '../../external/rcswitch-pi/send'),
                                 system_code,
                                 str(unit_code),
                                 str(command)]) == 0)

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def is_on(self):
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        self._state = STATE_ON
        Switch443._switch(self._group, self._device, 1)

    def turn_off(self, **kwargs):
        self._state = STATE_OFF
        Switch443._switch(self._group, self._device, 0)
