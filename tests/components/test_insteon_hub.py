""" The tests for the insteon hub component."""
# pylint: disable=proctected-access, too-many-public-methods
import unittest

from homeassistant.const import (
    STATE_UNKNOWN,
    STATE_HIGH,
)
from tests.common import get_test_home_assistant

import homeassistant.components.insteon_hub as insteon_hub

DEVICE_ID = 'device_id'
DEVICE_CATEGORY = 'device_category'
DEVICE_SUB_CATEGORY = 'device_sub_category'
DEVICE_NAME = 'device_name'


class Device(object):
    DeviceID = None
    DevCat = None
    SubCat = None
    DeviceName = None

    command_responses = {}

    def __init__(self, props):
        self.DeviceID = (props[DEVICE_ID]
                         if DEVICE_ID in props
                         else None)
        self.DevCat = (props[DEVICE_CATEGORY]
                       if DEVICE_CATEGORY in props
                       else None)
        self.SubCat = (props[DEVICE_SUB_CATEGORY]
                       if DEVICE_SUB_CATEGORY in props
                       else None)
        self.DeviceName = (props[DEVICE_NAME]
                           if DEVICE_NAME in props
                           else None)

    def send_command(self, command, payload=None, level=None, wait=False):
        if command not in self.command_responses:
            raise Exception('no mock response for command' + command)

        return self.command_responses[command]


class TestComponentsInsteonHub(unittest.TestCase):
    """ Test insteon hub component."""

    devices = [
        Device({
            DEVICE_CATEGORY: 1,
            DEVICE_SUB_CATEGORY: 5,
            DEVICE_NAME: 'A',
        }),
        Device({
            DEVICE_CATEGORY: 5,
            DEVICE_SUB_CATEGORY: 10,
            DEVICE_NAME: 'B',
        }),
    ]

    def setUp(self):
        """Test setup method"""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Test cleanup method"""
        self.hass.stop()

    def test_filter_no_sub(self):
        dev_filter = [{
            'DevCat': 1,
        }]
        filteredDevices = insteon_hub.filter_devices(self.devices, dev_filter)
        self.assertEquals(1, len(filteredDevices))
        self.assertEquals('A', filteredDevices[0].DeviceName)

    def test_filter(self):
        dev_filter = [{
            'DevCat': 5,
            'SubCat': [1, 3, 10],
        }]
        filteredDevices = insteon_hub.filter_devices(self.devices, dev_filter)

        self.assertEquals(1, len(filteredDevices))
        self.assertEquals('B', filteredDevices[0].DeviceName)


class TestInsteonDevice(unittest.TestCase):
    """ Tests around the inteon device class."""

    node = Device({
        DEVICE_ID: '123',
        DEVICE_NAME: 'A',
        DEVICE_CATEGORY: 1,
        DEVICE_SUB_CATEGORY: 1})

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_init(self):
        device = insteon_hub.InsteonDevice(self.node)

        self.assertEquals(self.node.DeviceID, device.unique_id)
        self.assertEquals(self.node.DeviceName, device.name)

    def test_is_successful(self):
        self.assertEquals(True,
                          insteon_hub.InsteonDevice.is_successful(
                              {'status': 'succeeded'}))
        self.assertEquals(False,
                          insteon_hub.InsteonDevice.is_successful(
                              {'status': 'failed'}))
        self.assertEquals(False,
                          insteon_hub.InsteonDevice.is_successful({}))


class TestInsteonToggleDevice(TestInsteonDevice):

    def setUp(self):
        self.node.command_responses = {
            'on': {
                'status': 'succeeded',
                'response': {
                    'level': 99
                }
            },
            'off': {
                'status': 'succeeded',
                'response': {
                    'level': 0
                }
            },
            'get_status': {
                'status': 'succeeded',
                'response': {
                    'level': 99
                }
            },
        }

    def test_update(self):
        device = insteon_hub.InsteonToggleDevice(self.node)

        device.update()

        self.assertEquals(99, device._value)

    def test_get_level(self):
        device = insteon_hub.InsteonToggleDevice(self.node)

        self.assertEquals(42,
                          device.get_level({
                              'status': 'succeeded',
                              'response': {'level': 42}
                          }))
        self.assertEquals(0, device.get_level({}))

    def test_is_on(self):
        device = insteon_hub.InsteonToggleDevice(self.node)
        self.assertEquals(False, device.is_on)
        device.turn_on()
        self.assertEquals(True, device.is_on)

    def test_turn_on(self):
        device = insteon_hub.InsteonToggleDevice(self.node)

        device.turn_on()

        self.assertEquals(99, device._value)

    def test_turn_off(self):
        device = insteon_hub.InsteonToggleDevice(self.node)

        device.turn_off()

        self.assertEquals(0, device._value)


class TestInsteonFanDevice(TestInsteonDevice):
    def setUp(self):
        self.node.command_responses = {
            'get_status': {
                'response': {
                    'level': 99
                },
                'status': 'succeeded'
            },
            'fan': {
                'status': 'succeeded'
            }
        }

    def test_update(self):
        device = insteon_hub.InsteonFanDevice(self.node)

        device.update()

        self.assertEquals(STATE_UNKNOWN, device.state)

    def test_set_value(self):
        device = insteon_hub.InsteonFanDevice(self.node)

        device.set_value(STATE_HIGH)

        self.assertEquals(STATE_HIGH, device.state)
