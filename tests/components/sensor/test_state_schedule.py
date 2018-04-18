"""The test for the state schedule sensor platform."""
import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component
from homeassistant.util import dt
from tests.common import get_test_home_assistant, fire_time_changed

SINGLE_LINE_CONFIG = {'sensor': {
    'platform': 'state_schedule',
    'name': 'test',
    'schedule': "Mon-Fri: 11:00-17:00"
}}
MULTI_LINE_CONFIG = {'sensor': {
    'platform': 'state_schedule',
    'name': 'test',
    'schedule': [
        "Mon-Fri: 11:00-17:00",
        "Sat-Sun: 01:00=warm, 03:00=hot, 09:00=off"
    ]
}}
SATURDAY_IN_DST = dt.parse_datetime('2018-03-31T02:47:19-04:00')


class TestStateScheduleSensor(unittest.TestCase):
    """Test the StateSchedule sensor."""

    def setup_method(self, method):
        """Set things up to be run when tests are started."""
        self.hass = get_test_home_assistant()

        # Switch timezone to New York so we make sure things work as expected
        self.DEFAULT_TIME_ZONE = dt.DEFAULT_TIME_ZONE
        new_tz = dt.get_time_zone('America/New_York')
        assert new_tz is not None
        dt.set_default_time_zone(new_tz)

    def teardown_method(self, method):
        """Stop everything that was started."""
        dt.set_default_time_zone(self.DEFAULT_TIME_ZONE)
        self.hass.stop()

    @patch('homeassistant.util.dt.now', return_value=SATURDAY_IN_DST)
    def test_platform_setup_single_line(self, _):
        """Test setting up a StateSchedule."""
        assert setup_component(self.hass, 'sensor', SINGLE_LINE_CONFIG)

        state = self.hass.states.get('sensor.test')
        self.assertEqual('off', state.state)
        self.assertEqual('Mon-Fri: 11:00-17:00',
                         state.attributes.get('schedule'))

    @patch('homeassistant.util.dt.now', return_value=SATURDAY_IN_DST)
    def test_platform_setup_multi_line(self, _):
        """Test setting up a StateSchedule with multiple schedule entries."""
        assert setup_component(self.hass, 'sensor', MULTI_LINE_CONFIG)

        state = self.hass.states.get('sensor.test')
        self.assertEqual('warm', state.state)
        self.assertEqual('Mon-Fri: 11:00-17:00; Sat-Sun: 01:00=warm, ' +
                         '03:00=hot, 09:00=off',
                         state.attributes.get('schedule'))

    @patch('homeassistant.util.dt.now', return_value=SATURDAY_IN_DST)
    def test_state_attributes_set(self, _):
        """Test state attributes are set correctly on startup."""
        assert setup_component(self.hass, 'sensor', SINGLE_LINE_CONFIG)

        state = self.hass.states.get('sensor.test')
        self.assertEqual('off', state.state)
        self.assertEqual('Mon-Fri: 11:00-17:00',
                         state.attributes.get('schedule'))
        self.assertEqual('test', state.attributes.get('friendly_name'))
        self.assertEqual('2018-03-31T02:47:19-04:00',
                         state.attributes.get('last updated'))
        self.assertEqual('2018-04-01T00:00:00-04:00',
                         state.attributes.get('next update'))
        self.assertEqual('2018-03-30T17:00:00-04:00',
                         state.attributes.get('last state change'))

    @patch('homeassistant.util.dt.now', return_value=SATURDAY_IN_DST)
    def test_state_changes_over_time(self, _):
        """Test state changes correctly as time moves forward."""
        assert setup_component(self.hass, 'sensor', MULTI_LINE_CONFIG)

        self.assertEqual('warm', self.hass.states.get('sensor.test').state)

        self._advance_time('2018-03-31T04:00:00-04:00')
        state = self.hass.states.get('sensor.test')
        self.assertEqual('hot', state.state)
        self.assertEqual('2018-03-31T09:00:00-04:00',
                         state.attributes.get('next update'))

        # After all events in a day, next update should be midnight
        self._advance_time('2018-03-31T14:00:00-04:00')
        state = self.hass.states.get('sensor.test')
        self.assertEqual('off', state.state)
        self.assertEqual('2018-04-01T00:00:00-04:00',
                         state.attributes.get('next update'))

        self._advance_time('2018-04-02T01:00:00-04:00')
        state = self.hass.states.get('sensor.test')
        self.assertEqual('off', state.state)
        self.assertEqual('2018-04-02T11:00:00-04:00',
                         state.attributes.get('next update'))

        self._advance_time('2018-04-02T12:00:00-04:00')
        state = self.hass.states.get('sensor.test')
        self.assertEqual('on', state.state)
        self.assertEqual('2018-04-02T17:00:00-04:00',
                         state.attributes.get('next update'))

    def _advance_time(self, time_str):
        """Convenience function."""
        fire_time_changed(self.hass, dt.parse_datetime(time_str))
        self.hass.block_till_done()
