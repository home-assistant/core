"""Tests for fan platforms."""

import unittest

from homeassistant.components.fan import FanEntity
import pytest


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
        assert 'on' == self.fan.state
        assert 0 == len(self.fan.speed_list)
        assert 0 == self.fan.supported_features
        assert {'speed_list': []} == self.fan.state_attributes
        # Test set_speed not required
        self.fan.oscillate(True)
        with pytest.raises(NotImplementedError):
            self.fan.set_speed('slow')
        with pytest.raises(NotImplementedError):
            self.fan.turn_on()
        with pytest.raises(NotImplementedError):
            self.fan.turn_off()
