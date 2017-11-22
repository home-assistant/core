"""The test for the History Average sensor platform."""
from datetime import timedelta
from collections import defaultdict
import logging
import unittest
from unittest.mock import patch

from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.components.sensor.history_average\
     import HistoryAverageSensor
from homeassistant.core import State
from homeassistant.helpers.template import Template
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util
from tests.common import (
    init_recorder_component,
    get_test_home_assistant,
    mock_state_change_event
)

_LOGGER = logging.getLogger(__name__)


class TestHistoryAverageSensor(unittest.TestCase):
    """Test the History Average sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.recorder = defaultdict(list)
        init_recorder_component(self.hass)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def start_hass(self):
        """Start hass and wait for recorder to finish."""
        self.recorder = defaultdict(list)
        self.hass.start()
        self.wait_recording_done()

    def wait_recording_done(self):
        """Block till recording is done."""
        self.hass.block_till_done()
        self.hass.data[DATA_INSTANCE].block_till_done()

    def test_setup(self):
        """Test the history average sensor setup."""
        self.start_hass()

        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_average',
                'entity_id': 'somesensor.unreal',
                'start': '{{ now().replace(hour=0)'
                         '.replace(minute=0).replace(second=0) }}',
                'duration': '02:00',
                'name': 'Test',
            }
        }

        self.assertTrue(setup_component(self.hass, 'sensor', config))

        state = self.hass.states.get('sensor.test').as_dict()
        self.assertEqual(state['state'], '0')

    def test_period_parsing(self):
        """Test the conversion from templates to period."""
        self.start_hass()

        today = Template('{{ now().replace(hour=0).replace(minute=0)'
                         '.replace(second=0) }}', self.hass)
        duration = timedelta(hours=2, minutes=1)

        sensor1 = HistoryAverageSensor(
            self.hass, 'test', today, None, duration, 'Test', '')
        sensor2 = HistoryAverageSensor(
            self.hass, 'test', None, today, duration, 'Test', '')

        yield from sensor1.async_update_period()
        sensor1_start, sensor1_end = sensor1.get_period()
        yield from sensor2.async_update_period()
        sensor2_start, sensor2_end = sensor2.get_period()

        # Start = 00:00:00
        self.assertEqual(sensor1_start.hour, 0)
        self.assertEqual(sensor1_start.minute, 0)
        self.assertEqual(sensor1_start.second, 0)

        # End = 02:01:00
        self.assertEqual(sensor1_end.hour, 2)
        self.assertEqual(sensor1_end.minute, 1)
        self.assertEqual(sensor1_end.second, 0)

        # Start = 21:59:00
        self.assertEqual(sensor2_start.hour, 21)
        self.assertEqual(sensor2_start.minute, 59)
        self.assertEqual(sensor2_start.second, 0)

        # End = 00:00:00
        self.assertEqual(sensor2_end.hour, 0)
        self.assertEqual(sensor2_end.minute, 0)
        self.assertEqual(sensor2_end.second, 0)

    def _set_state(self, entity_id, value, now, timestamp):
        """Set entity state state."""
        state = State(entity_id, value, None, timestamp, timestamp)
        _LOGGER.debug("set_state: " + str(value) + " @ " + str(timestamp))
        mock_state_change_event(self.hass, state)
        self.wait_recording_done()
        self.recorder[entity_id].append(state)

    def _add_test_states(self, entity_id, now):
        """Add multiple states to history for testing."""
        # start hass before recording states
        self.start_hass()

        # Start     t0        t1        t2        End (now)
        # |--20min--|--20min--|--10min--|--10min--|
        # |----?----|----1----|---10----|---100---|

        time0 = now - timedelta(minutes=40)
        self._set_state(entity_id, 1, now, time0)

        time1 = now - timedelta(minutes=20)
        self._set_state(entity_id, 10, now, time1)

        time2 = now - timedelta(minutes=10)
        self._set_state(entity_id, 100, now, time2)

    def _setup_sensor(self, sensor, sensor_source, now, start_offset,
                      end_offset):
        """Setup sensor."""
        now_string = str(dt_util.as_timestamp(now))
        start = '{{ ' + now_string + ' - ' + start_offset + ' }}'
        end = '{{ ' + now_string + ' - ' + end_offset + ' }}'

        with patch('homeassistant.components.history.'
                   'state_changes_during_period', return_value=self.recorder):
            assert setup_component(self.hass, 'sensor', {
                'history': {
                },
                'sensor': {
                    'platform': 'history_average',
                    'name': sensor,
                    'entity_id': sensor_source,
                    'start': start,
                    'end': end,
                }
            })

    def _get_sensor_state(self, sensor, now):
        """Return current value of sensor."""
        state = self.hass.states.get('sensor.' + sensor)
        return state

    def test_history_loading(self):
        """Test the loading of historical data on sensor startup."""
        now = dt_util.utcnow()
        sensor = 'sensor_history'
        sensor_source = 'sensor.source_history'

        # add states before setting up the sensor
        self._add_test_states(sensor_source, now)
        self._setup_sensor(sensor, sensor_source, now, '3000', '0')

        state = self._get_sensor_state(sensor, now)
        self.assertEqual(float(state.state), 28)

    def test_history_loading_at_end(self):
        """Test the loading of historical data, reading off end."""
        now = dt_util.utcnow()
        sensor = 'sensor_end'
        sensor_source = 'sensor.source_end'

        # add state before setting up the sensor
        self.start_hass()
        time = now - timedelta(minutes=10)
        self._set_state(sensor_source, 100, now, time)
        self._setup_sensor(sensor, sensor_source, now, '1', '0')

        state = self._get_sensor_state(sensor, now)
        self.assertEqual(float(state.state), 100)

    def test_state_changes(self):
        """Test updates to source data on sensor."""
        now = dt_util.utcnow()
        sensor = 'sensor_state'
        sensor_source = 'sensor.source_state'

        # sensor state is zero at setup, before state changes
        self._setup_sensor(sensor, sensor_source, now, '3600', '0')
        state = self._get_sensor_state(sensor, now)
        self.assertEqual(float(state.state), 0)

        # trigger state changes after sensor setup
        self._add_test_states(sensor_source, now)

        state = self._get_sensor_state(sensor, now)
        self.assertEqual(float(state.state), 28)

    def test_range_1(self):
        """Test range: (t0 - 1 second) to End."""
        now = dt_util.utcnow()
        sensor = 'sensor1'
        sensor_source = 'sensor.source1'
        self._add_test_states(sensor_source, now)
        self._setup_sensor(sensor, sensor_source, now, '2401', '0')
        state = self._get_sensor_state(sensor, now)
        self.assertEqual(float(state.state), 28)

    def test_range_2(self):
        """Test range: (t1 - 1 second) to (t2 + 1 second)."""
        now = dt_util.utcnow()
        sensor = 'sensor2'
        sensor_source = 'sensor.source2'
        self._setup_sensor(sensor, sensor_source, now, '1201', '599')
        self._add_test_states(sensor_source, now)
        state = self._get_sensor_state(sensor, now)
        self.assertEqual(float(state.state), 10.13)

    def test_range_3(self):
        """Test range: (t2 + 1 second) to End."""
        now = dt_util.utcnow()
        sensor = 'sensor3'
        sensor_source = 'sensor.source3'
        self._setup_sensor(sensor, sensor_source, now, '599', '0')
        self._add_test_states(sensor_source, now)
        state = self._get_sensor_state(sensor, now)
        self.assertEqual(float(state.state), 100)

    def test_range_4_from_history(self):
        """Test range: (t0 + 1 second) to End (loaded from history)."""
        now = dt_util.utcnow()
        sensor = 'sensor4_history'
        sensor_source = 'sensor.source4_history'
        self._add_test_states(sensor_source, now)
        self._setup_sensor(sensor, sensor_source, now, '2399', '0')
        state = self._get_sensor_state(sensor, now)
        self.assertEqual(float(state.state), 28.01)

    def test_range_4_from_updates(self):
        """Test range: (t0 + 1 second) to End (async updates)."""
        now = dt_util.utcnow()
        sensor = 'sensor4_updates'
        sensor_source = 'sensor.source4_updates'
        self._setup_sensor(sensor, sensor_source, now, '2399', '0')
        self._add_test_states(sensor_source, now)
        state = self._get_sensor_state(sensor, now)
        self.assertEqual(float(state.state), 28.01)

    def test_wrong_date(self):
        """Test when start or end value is not a timestamp or a date."""
        self.start_hass()

        good = Template('{{ now() }}', self.hass)
        bad = Template('{{ TEST }}', self.hass)

        sensor1 = HistoryAverageSensor(
            self.hass, 'test', good, bad, None, 'time', 'Test')
        sensor2 = HistoryAverageSensor(
            self.hass, 'test', bad, good, None, 'time', 'Test')

        before_update1 = sensor1.get_period()
        before_update2 = sensor2.get_period()

        yield from sensor1.async_update_period()
        yield from sensor2.async_update_period()

        self.assertEqual(before_update1, sensor1.get_period())
        self.assertEqual(before_update2, sensor2.get_period())

    def test_wrong_duration(self):
        """Test when duration value is not a timedelta."""
        self.start_hass()

        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_average',
                'entity_id': 'sensor.source',
                'name': 'Test',
                'start': '{{ now() }}',
                'duration': 'TEST',
            }
        }

        setup_component(self.hass, 'sensor', config)
        self.assertEqual(self.hass.states.get('sensor.test'), None)
        self.assertRaises(TypeError,
                          setup_component(self.hass, 'sensor', config))

    def test_bad_template(self):
        """Test Exception when the template cannot be parsed."""
        self.start_hass()

        bad = Template('{{ x - 12 }}', self.hass)  # x is undefined
        duration = '01:00'

        sensor1 = HistoryAverageSensor(
            self.hass, 'test', bad, None, duration, 'time', 'Test')
        sensor2 = HistoryAverageSensor(
            self.hass, 'test', None, bad, duration, 'time', 'Test')

        before_update1 = sensor1.get_period()
        before_update2 = sensor2.get_period()

        yield from sensor1.async_update_period()
        yield from sensor2.async_update_period()

        self.assertEqual(before_update1, sensor1.get_period())
        self.assertEqual(before_update2, sensor2.get_period())

    def test_not_enough_arguments(self):
        """Test config when not enough arguments provided."""
        self.start_hass()

        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_average',
                'entity_id': 'sensor.source',
                'name': 'Test',
                'start': '{{ now() }}',
            }
        }

        setup_component(self.hass, 'sensor', config)
        self.assertEqual(self.hass.states.get('sensor.test'), None)
        self.assertRaises(TypeError,
                          setup_component(self.hass, 'sensor', config))

    def test_too_many_arguments(self):
        """Test config when too many arguments provided."""
        self.start_hass()

        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_average',
                'entity_id': 'sensor.source',
                'name': 'Test',
                'start': '{{ as_timestamp(now()) - 3600 }}',
                'end': '{{ now() }}',
                'duration': '01:00',
            }
        }

        setup_component(self.hass, 'sensor', config)
        self.assertEqual(self.hass.states.get('sensor.test'), None)
        self.assertRaises(TypeError,
                          setup_component(self.hass, 'sensor', config))
