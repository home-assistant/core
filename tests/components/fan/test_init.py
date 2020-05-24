"""Tests for fan platforms."""

import unittest

import pytest

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
        assert self.fan.state == "off"
        assert len(self.fan.speed_list) == 0
        assert self.fan.supported_features == 0
        assert self.fan.capability_attributes == {}
        # Test set_speed not required
        self.fan.oscillate(True)
        with pytest.raises(NotImplementedError):
            self.fan.set_speed("slow")
        with pytest.raises(NotImplementedError):
            self.fan.turn_on()
        with pytest.raises(NotImplementedError):
            self.fan.turn_off()
