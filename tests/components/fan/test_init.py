"""Tests for fan platforms."""

import unittest

from homeassistant.components.fan import FanEntity


class BaseFan(FanEntity):
    """Implementation of the abstract FanEntity."""

    def __init__(self):
        """Initialize the fan."""
        pass


class TestFanEntity(unittest.TestCase):
    """Test coverage for base fan entity class."""

    def setUp(self):
        """Set up test data."""
        self.fan = BaseFan()

    def tearDown(self):
        """Tear down unit test data."""
        self.fan = None

    def test_fanentity(self):
        """Test fan entity methods."""
        self.assertEqual('on', self.fan.state)
        self.assertEqual(0, len(self.fan.speed_list))
        self.assertEqual(0, self.fan.supported_features)
        self.assertEqual({'speed_list': []}, self.fan.state_attributes)
        # Test set_speed not required
        self.fan.oscillate(True)
        with self.assertRaises(NotImplementedError):
            self.fan.set_speed('slow')
        with self.assertRaises(NotImplementedError):
            self.fan.turn_on()
        with self.assertRaises(NotImplementedError):
            self.fan.turn_off()
