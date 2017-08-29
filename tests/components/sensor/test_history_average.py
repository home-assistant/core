"""The test for the History Average sensor platform."""
from datetime import timedelta
import unittest
from unittest.mock import patch

from homeassistant.components import recorder
from homeassistant.components.sensor.history_average\
     import HistoryAverageSensor
from homeassistant.helpers.template import Template
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util
from tests.common import init_recorder_component, get_test_home_assistant


class TestHistoryAverageSensor(unittest.TestCase):
    """Test the History Average sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def init_recorder(self):
        """Initialize the recorder."""
        init_recorder_component(self.hass)
        self.hass.start()
        self.wait_recording_done()

    def wait_recording_done(self):
        """Block till recording is done."""
        self.hass.block_till_done()
        self.hass.data[recorder.DATA_INSTANCE].block_till_done()

    def test_setup(self):
        """Test the history average sensor setup."""
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
        today = Template('{{ now().replace(hour=0).replace(minute=0)'
                         '.replace(second=0) }}', self.hass)
        duration = timedelta(hours=2, minutes=1)

        sensor1 = HistoryAverageSensor(
            self.hass, 'test', today, None, duration, 'Test', '')
        sensor2 = HistoryAverageSensor(
            self.hass, 'test', None, today, duration, 'Test', '')

        sensor1.update_period()
        sensor1_start, sensor1_end = sensor1._period
        sensor2.update_period()
        sensor2_start, sensor2_end = sensor2._period

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

    def _add_test_states(self, now):
        """Add multiple states to history for testing."""
        self.init_recorder()

        def set_state(entity_id, state, timestamp):
            """Set the state."""
            with patch('homeassistant.components.recorder.dt_util.utcnow',
                       return_value=timestamp):
                self.hass.states.set(entity_id, state)
                self.wait_recording_done()

        # Start     t0        t1        t2        End
        # |--20min--|--20min--|--10min--|--10min--|
        # |----?----|----1----|---10----|---100---|

        time0 = now - timedelta(minutes=40)
        set_state('binary_sensor.test_id', 1, time0)

        time1 = now - timedelta(minutes=20)
        set_state('binary_sensor.test_id', 10, time1)

        time2 = now - timedelta(minutes=10)
        set_state('binary_sensor.test_id', 100, time2)

    def test_measure(self):
        """Test the history average sensor measurements."""
        # TODO: removing the "+ timedelta" breaks the recorder, and I don't
        #      know why - filing a bug in HA to track.
        now = dt_util.utcnow() + timedelta(hours=1)
        self._add_test_states(now)
        now_string = str(dt_util.as_timestamp(now))

        # range: (t0 - 1 second) to End
        start = Template('{{ ' + now_string + ' - 2401 }}', self.hass)
        end = Template('{{ ' + now_string + ' }}', self.hass)
        sensor1 = HistoryAverageSensor(
            self.hass, 'binary_sensor.test_id', start, end, None, 'Test', '%')

        # range: full range, including unknown values at the start
        start = Template('{{ ' + now_string + ' - 3600 }}', self.hass)
        end = Template('{{ ' + now_string + ' }}', self.hass)
        sensor2 = HistoryAverageSensor(
            self.hass, 'binary_sensor.test_id', start, end, None, 'Test', '$')

        # range: (t1 - 1 second) to (t2 + 1 second)
        start = Template('{{ ' + now_string + ' - 1201 }}', self.hass)
        end = Template('{{ ' + now_string + ' - 599 }}', self.hass)
        sensor3 = HistoryAverageSensor(
            self.hass, 'binary_sensor.test_id', start, end, None, 'Test', '')

        # range: (t2 + 1 second) to End
        start = Template('{{ ' + now_string + ' - 599 }}', self.hass)
        end = Template('{{ ' + now_string + ' }}', self.hass)
        sensor4 = HistoryAverageSensor(
            self.hass, 'binary_sensor.test_id', start, end, None, 'Test', '')

        with patch(
            'homeassistant.components.sensor.history_average.dt_util.utcnow',
            return_value=now):
            sensor1.update()
            sensor2.update()
            sensor3.update()
            sensor4.update()

        self.assertEqual(sensor1.state, 28)
        self.assertEqual(sensor2.state, 28)
        self.assertEqual(sensor3.state, 10.13)
        self.assertEqual(sensor4.state, 100)

        self.assertEqual(sensor1._unit_of_measurement, '%')
        self.assertEqual(sensor2._unit_of_measurement, '$')
        self.assertEqual(sensor3._unit_of_measurement, '')

    def test_wrong_date(self):
        """Test when start or end value is not a timestamp or a date."""
        good = Template('{{ now() }}', self.hass)
        bad = Template('{{ TEST }}', self.hass)

        sensor1 = HistoryAverageSensor(
            self.hass, 'test', good, bad, None, 'time', 'Test')
        sensor2 = HistoryAverageSensor(
            self.hass, 'test', bad, good, None, 'time', 'Test')

        before_update1 = sensor1._period
        before_update2 = sensor2._period

        sensor1.update_period()
        sensor2.update_period()

        self.assertEqual(before_update1, sensor1._period)
        self.assertEqual(before_update2, sensor2._period)

    def test_wrong_duration(self):
        """Test when duration value is not a timedelta."""
        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_average',
                'entity_id': 'binary_sensor.test_id',
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
        bad = Template('{{ x - 12 }}', self.hass)  # x is undefined
        duration = '01:00'

        sensor1 = HistoryAverageSensor(
            self.hass, 'test', bad, None, duration, 'time', 'Test')
        sensor2 = HistoryAverageSensor(
            self.hass, 'test', None, bad, duration, 'time', 'Test')

        before_update1 = sensor1._period
        before_update2 = sensor2._period

        sensor1.update_period()
        sensor2.update_period()

        self.assertEqual(before_update1, sensor1._period)
        self.assertEqual(before_update2, sensor2._period)

    def test_not_enough_arguments(self):
        """Test config when not enough arguments provided."""
        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_average',
                'entity_id': 'binary_sensor.test_id',
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
        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_average',
                'entity_id': 'binary_sensor.test_id',
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
