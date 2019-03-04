"""The tests for Kira sensor platform."""
import unittest
from unittest.mock import patch

from homeassistant.components.sensor import time_date as time_date
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant


class TestTimeDateSensor(unittest.TestCase):
    """Tests the Kira Sensor platform."""

    # pylint: disable=invalid-name
    DEVICES = []

    def add_entities(self, devices):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.DEFAULT_TIME_ZONE = dt_util.DEFAULT_TIME_ZONE

    def tearDown(self):
        """Stop everything that was started."""
        dt_util.set_default_time_zone(self.DEFAULT_TIME_ZONE)
        self.hass.stop()

    # pylint: disable=protected-access
    def test_intervals(self):
        """Test timing intervals of sensors."""
        device = time_date.TimeDateSensor(self.hass, 'time')
        now = dt_util.utc_from_timestamp(45)
        next_time = device.get_next_interval(now)
        assert next_time == dt_util.utc_from_timestamp(60)

        device = time_date.TimeDateSensor(self.hass, 'beat')
        now = dt_util.utc_from_timestamp(29)
        next_time = device.get_next_interval(now)
        assert next_time == dt_util.utc_from_timestamp(86.4)

        device = time_date.TimeDateSensor(self.hass, 'date_time')
        now = dt_util.utc_from_timestamp(1495068899)
        next_time = device.get_next_interval(now)
        assert next_time == dt_util.utc_from_timestamp(1495068900)

        now = dt_util.utcnow()
        device = time_date.TimeDateSensor(self.hass, 'time_date')
        next_time = device.get_next_interval()
        assert next_time > now

    def test_states(self):
        """Test states of sensors."""
        now = dt_util.utc_from_timestamp(1495068856)
        device = time_date.TimeDateSensor(self.hass, 'time')
        device._update_internal_state(now)
        assert device.state == "00:54"

        device = time_date.TimeDateSensor(self.hass, 'date')
        device._update_internal_state(now)
        assert device.state == "2017-05-18"

        device = time_date.TimeDateSensor(self.hass, 'time_utc')
        device._update_internal_state(now)
        assert device.state == "00:54"

        device = time_date.TimeDateSensor(self.hass, 'beat')
        device._update_internal_state(now)
        assert device.state == "@079"

    # pylint: disable=no-member
    def test_timezone_intervals(self):
        """Test date sensor behavior in a timezone besides UTC."""
        new_tz = dt_util.get_time_zone('America/New_York')
        assert new_tz is not None
        dt_util.set_default_time_zone(new_tz)

        device = time_date.TimeDateSensor(self.hass, 'date')
        now = dt_util.utc_from_timestamp(50000)
        next_time = device.get_next_interval(now)
        # start of local day in EST was 18000.0
        # so the second day was 18000 + 86400
        assert next_time.timestamp() == 104400

        new_tz = dt_util.get_time_zone('America/Edmonton')
        assert new_tz is not None
        dt_util.set_default_time_zone(new_tz)
        now = dt_util.parse_datetime('2017-11-13 19:47:19-07:00')
        device = time_date.TimeDateSensor(self.hass, 'date')
        next_time = device.get_next_interval(now)
        assert (next_time.timestamp() ==
                dt_util.as_timestamp('2017-11-14 00:00:00-07:00'))

    @patch('homeassistant.util.dt.utcnow',
           return_value=dt_util.parse_datetime('2017-11-14 02:47:19-00:00'))
    def test_timezone_intervals_empty_parameter(self, _):
        """Test get_interval() without parameters."""
        new_tz = dt_util.get_time_zone('America/Edmonton')
        assert new_tz is not None
        dt_util.set_default_time_zone(new_tz)
        device = time_date.TimeDateSensor(self.hass, 'date')
        next_time = device.get_next_interval()
        assert (next_time.timestamp() ==
                dt_util.as_timestamp('2017-11-14 00:00:00-07:00'))

    def test_icons(self):
        """Test attributes of sensors."""
        device = time_date.TimeDateSensor(self.hass, 'time')
        assert device.icon == "mdi:clock"
        device = time_date.TimeDateSensor(self.hass, 'date')
        assert device.icon == "mdi:calendar"
        device = time_date.TimeDateSensor(self.hass, 'date_time')
        assert device.icon == "mdi:calendar-clock"
