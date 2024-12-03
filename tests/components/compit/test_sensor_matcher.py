"""Tests for the SensorMatcher class."""

import unittest
from unittest.mock import MagicMock

from compit_inext_api import Param, Parameter

from homeassistant.components.compit.sensor_matcher import SensorMatcher
from homeassistant.const import Platform


class TestSensorMatcher(unittest.TestCase):
    """Tests for the SensorMatcher class."""

    def test_get_platform_none_value(self):
        """Test get_platform with None value."""
        param = MagicMock(spec=Parameter)
        value = None
        result = SensorMatcher.get_platform(param, value)
        assert result is None

    def test_get_platform_hidden_value(self):
        """Test get_platform with hidden value."""
        param = MagicMock(spec=Parameter)
        value = MagicMock(spec=Param)
        value.hidden = True
        result = SensorMatcher.get_platform(param, value)
        assert result is None

    def test_get_platform_read_only(self):
        """Test get_platform with read only parameter."""
        param = MagicMock(spec=Parameter)
        param.readWrite = "R"
        value = MagicMock(spec=Param)
        value.hidden = False
        result = SensorMatcher.get_platform(param, value)
        assert result == Platform.SENSOR

    def test_get_platform_number(self):
        """Test get_platform with number parameter."""
        param = MagicMock(spec=Parameter)
        param.readWrite = "RW"
        param.min_value = 0
        param.max_value = 100
        value = MagicMock(spec=Param)
        value.hidden = False
        result = SensorMatcher.get_platform(param, value)
        assert result == Platform.NUMBER

    def test_get_platform_select(self):
        """Test get_platform with select parameter."""
        param = MagicMock(spec=Parameter)
        param.readWrite = "RW"
        param.min_value = None
        param.max_value = None
        param.details = "Some details"
        value = MagicMock(spec=Param)
        value.hidden = False
        result = SensorMatcher.get_platform(param, value)
        assert result == Platform.SELECT

    def test_get_platform_none(self):
        """Test get_platform with no match."""
        param = MagicMock(spec=Parameter)
        param.readWrite = "RW"
        param.min_value = None
        param.max_value = None
        param.details = None
        value = MagicMock(spec=Param)
        value.hidden = False
        result = SensorMatcher.get_platform(param, value)
        assert result is None


if __name__ == "__main__":
    unittest.main()
