"""Tests for the insteon hub fan platform."""
import unittest

from homeassistant.const import (STATE_OFF, STATE_ON)
from homeassistant.components.fan import (SPEED_LOW, SPEED_MED, SPEED_HIGH,
                                          ATTR_SPEED)
from homeassistant.components.fan.insteon_hub import (InsteonFanDevice,
                                                      SUPPORT_SET_SPEED)


class Node(object):
    """Fake insteon node."""

    def __init__(self, name, id, dev_cat, sub_cat):
        """Initialize fake insteon node."""
        self.DeviceName = name
        self.DeviceID = id
        self.DevCat = dev_cat
        self.SubCat = sub_cat
        self.response = None

    def send_command(self, command, payload, level, wait):
        """Send fake command."""
        return self.response


class TestInsteonHubFanDevice(unittest.TestCase):
    """Test around insteon hub fan device methods."""

    _NODE = Node('device', '12345', '1', '46')

    def setUp(self):
        """Initialize test data."""
        self._DEVICE = InsteonFanDevice(self._NODE)

    def tearDown(self):
        """Tear down test data."""
        self._DEVICE = None

    def test_properties(self):
        """Test basic properties."""
        self.assertEqual(self._NODE.DeviceName, self._DEVICE.name)
        self.assertEqual(self._NODE.DeviceID, self._DEVICE.unique_id)
        self.assertEqual(SUPPORT_SET_SPEED, self._DEVICE.supported_features)

        for speed in [STATE_OFF, SPEED_LOW, SPEED_MED, SPEED_HIGH]:
            self.assertIn(speed, self._DEVICE.speed_list)

    def test_turn_on(self):
        """Test the turning on device."""
        self._NODE.response = {
            'status': 'succeeded'
        }
        self.assertEqual(STATE_OFF, self._DEVICE.state)
        self._DEVICE.turn_on()

        self.assertEqual(STATE_ON, self._DEVICE.state)

        self._DEVICE.turn_on(SPEED_MED)

        self.assertEqual(STATE_ON, self._DEVICE.state)
        self.assertEqual(SPEED_MED, self._DEVICE.state_attributes[ATTR_SPEED])

    def test_turn_off(self):
        """Test turning off device."""
        self._NODE.response = {
            'status': 'succeeded'
        }
        self.assertEqual(STATE_OFF, self._DEVICE.state)
        self._DEVICE.turn_on()
        self.assertEqual(STATE_ON, self._DEVICE.state)
        self._DEVICE.turn_off()
        self.assertEqual(STATE_OFF, self._DEVICE.state)
