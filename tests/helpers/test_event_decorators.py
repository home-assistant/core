"""Test event decorator helpers."""
# pylint: disable=protected-access,too-many-public-methods
# pylint: disable=too-few-public-methods
import unittest
from datetime import datetime, timedelta

from astral import Astral

import homeassistant.core as ha
import homeassistant.util.dt as dt_util
from homeassistant.helpers import event_decorators
from homeassistant.helpers.event_decorators import (
    track_time_change, track_utc_time_change, track_state_change,
    track_sunrise, track_sunset)
from homeassistant.components import sun

from tests.common import get_test_home_assistant


class TestEventDecoratorHelpers(unittest.TestCase):
    """Test the Home Assistant event helpers."""

    def setUp(self):     # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.states.set("light.Bowl", "on")
        self.hass.states.set("switch.AC", "off")

        event_decorators.HASS = self.hass

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()
        event_decorators.HASS = None

    def test_track_sunrise(self):
        """Test track sunrise decorator."""
        latitude = 32.87336
        longitude = 117.22743

        # Setup sun component
        self.hass.config.latitude = latitude
        self.hass.config.longitude = longitude
        sun.setup(self.hass, {sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

        # Get next sunrise/sunset
        astral = Astral()
        utc_now = dt_util.utcnow()

        mod = -1
        while True:
            next_rising = (astral.sunrise_utc(utc_now +
                           timedelta(days=mod), latitude, longitude))
            if next_rising > utc_now:
                break
            mod += 1

        # Use decorator
        runs = []
        decor = track_sunrise()
        decor(lambda x: runs.append(1))

        offset_runs = []
        offset = timedelta(minutes=30)
        decor = track_sunrise(offset)
        decor(lambda x: offset_runs.append(1))

        # Run tests
        self._send_time_changed(next_rising - offset)
        self.hass.block_till_done()
        self.assertEqual(0, len(runs))
        self.assertEqual(0, len(offset_runs))

        self._send_time_changed(next_rising)
        self.hass.block_till_done()
        self.assertEqual(1, len(runs))
        self.assertEqual(0, len(offset_runs))

        self._send_time_changed(next_rising + offset)
        self.hass.block_till_done()
        self.assertEqual(2, len(runs))
        self.assertEqual(1, len(offset_runs))

    def test_track_sunset(self):
        """Test track sunset decorator."""
        latitude = 32.87336
        longitude = 117.22743

        # Setup sun component
        self.hass.config.latitude = latitude
        self.hass.config.longitude = longitude
        sun.setup(self.hass, {sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

        # Get next sunrise/sunset
        astral = Astral()
        utc_now = dt_util.utcnow()

        mod = -1
        while True:
            next_setting = (astral.sunset_utc(utc_now +
                            timedelta(days=mod), latitude, longitude))
            if next_setting > utc_now:
                break
            mod += 1

        # Use decorator
        runs = []
        decor = track_sunset()
        decor(lambda x: runs.append(1))

        offset_runs = []
        offset = timedelta(minutes=30)
        decor = track_sunset(offset)
        decor(lambda x: offset_runs.append(1))

        # run tests
        self._send_time_changed(next_setting - offset)
        self.hass.block_till_done()
        self.assertEqual(0, len(runs))
        self.assertEqual(0, len(offset_runs))

        self._send_time_changed(next_setting)
        self.hass.block_till_done()
        self.assertEqual(1, len(runs))
        self.assertEqual(0, len(offset_runs))

        self._send_time_changed(next_setting + offset)
        self.hass.block_till_done()
        self.assertEqual(2, len(runs))
        self.assertEqual(1, len(offset_runs))

    def test_track_time_change(self):
        """Test tracking time change."""
        wildcard_runs = []
        specific_runs = []

        decor = track_time_change()
        decor(lambda x, y: wildcard_runs.append(1))

        decor = track_utc_time_change(second=[0, 30])
        decor(lambda x, y: specific_runs.append(1))

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 0))
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 15))
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(2, len(wildcard_runs))

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 30))
        self.hass.block_till_done()
        self.assertEqual(2, len(specific_runs))
        self.assertEqual(3, len(wildcard_runs))

    def test_track_state_change(self):
        """Test track_state_change."""
        # 2 lists to track how often our callbacks get called
        specific_runs = []
        wildcard_runs = []

        decor = track_state_change('light.Bowl', 'on', 'off')
        decor(lambda a, b, c, d: specific_runs.append(1))

        decor = track_state_change('light.Bowl', ha.MATCH_ALL, ha.MATCH_ALL)
        decor(lambda a, b, c, d: wildcard_runs.append(1))

        # Set same state should not trigger a state change/listener
        self.hass.states.set('light.Bowl', 'on')
        self.hass.block_till_done()
        self.assertEqual(0, len(specific_runs))
        self.assertEqual(0, len(wildcard_runs))

        # State change off -> on
        self.hass.states.set('light.Bowl', 'off')
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))

        # State change off -> off
        self.hass.states.set('light.Bowl', 'off', {"some_attr": 1})
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(2, len(wildcard_runs))

        # State change off -> on
        self.hass.states.set('light.Bowl', 'on')
        self.hass.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(3, len(wildcard_runs))

    def _send_time_changed(self, now):
        """Send a time changed event."""
        self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: now})
