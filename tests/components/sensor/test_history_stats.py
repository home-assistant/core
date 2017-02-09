"""The test for the History Statistics sensor platform."""
# pylint: disable=protected-access
import unittest
from datetime import timedelta
from unittest.mock import patch

import homeassistant.components.recorder as recorder
import homeassistant.core as ha
import homeassistant.util.dt as dt_util
from homeassistant.bootstrap import setup_component
from homeassistant.components.sensor.history_stats import HistoryStatsSensor
from homeassistant.helpers.template import Template
from tests.common import get_test_home_assistant


class TestHistoryStatsSensor(unittest.TestCase):
    """Test the History Statistics sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test the history statistics sensor setup."""
        self.init_recorder()
        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_stats',
                'entity_id': 'binary_sensor.test_id',
                'state': 'on',
                'start': '{{ now().replace(hour=0)'
                         '.replace(minute=0).replace(second=0) }}',
                'duration': '{{ 3600 * 2 + 60 }}',
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
        duration = Template('{{ 3600 * 2 + 60 }}', self.hass)

        sensor1 = HistoryStatsSensor(
            self.hass, 'test', 'on', today, None, duration, 'test')
        sensor2 = HistoryStatsSensor(
            self.hass, 'test', 'on', None, today, duration, 'test')

        sensor1.update_period()
        sensor2.update_period()

        self.assertEqual(
            sensor1.device_state_attributes['from'][-8:], '00:00:00')
        self.assertEqual(
            sensor1.device_state_attributes['to'][-8:], '02:01:00')
        self.assertEqual(
            sensor2.device_state_attributes['from'][-8:], '21:59:00')
        self.assertEqual(
            sensor2.device_state_attributes['to'][-8:], '00:00:00')

    def test_measure(self):
        """Test the history statistics sensor measure."""
        later = dt_util.utcnow() - timedelta(seconds=15)
        earlier = later - timedelta(minutes=30)

        fake_states = {
            'binary_sensor.test_id': [
                ha.State('binary_sensor.test_id', 'on', last_changed=earlier),
                ha.State('binary_sensor.test_id', 'off', last_changed=later),
            ]
        }

        start = Template('{{ as_timestamp(now()) - 3600 }}', self.hass)
        end = Template('{{ now() }}', self.hass)

        sensor1 = HistoryStatsSensor(
            self.hass, 'binary_sensor.test_id', 'on', start, end, None, 'Test')

        sensor2 = HistoryStatsSensor(
            self.hass, 'unknown.id', 'on', start, end, None, 'Test')

        with patch('homeassistant.components.history.'
                   'state_changes_during_period', return_value=fake_states):
            with patch('homeassistant.components.history.get_state',
                       return_value=None):
                sensor1.update()
                sensor2.update()

        self.assertEqual(sensor1.value, 0.5)
        self.assertEqual(sensor2.value, 0)
        self.assertEqual(sensor1.device_state_attributes['ratio'], '50.0%')

    def test_wrong_date(self):
        """Test when start or end value is not a timestamp or a date."""
        good = Template('{{ now() }}', self.hass)
        bad = Template('{{ TEST }}', self.hass)

        sensor1 = HistoryStatsSensor(
            self.hass, 'test', 'on', good, bad, None, 'Test')
        sensor2 = HistoryStatsSensor(
            self.hass, 'test', 'on', bad, good, None, 'Test')

        before_update1 = sensor1._period
        before_update2 = sensor2._period

        sensor1.update_period()
        sensor2.update_period()

        self.assertEqual(before_update1, sensor1._period)
        self.assertEqual(before_update2, sensor2._period)

    def test_wrong_duration(self):
        """Test when duration value is not a number."""
        start = Template('{{ as_timestamp(now()) - 24 * 3600 }}', self.hass)
        duration = Template('{{  now() }}', self.hass)

        sensor = HistoryStatsSensor(
            self.hass, 'test', 'on', start, None, duration, 'Test')

        before_update = sensor._period
        sensor.update_period()
        self.assertEqual(before_update, sensor._period)

    def test_bad_template(self):
        """Test Exception when the template cannot be parsed."""
        bad = Template('{{ x - 12 }}', self.hass)  # x is undefined
        good = Template('{{ now() }}', self.hass)
        good_duration = Template('{{ 3600 }}', self.hass)

        sensor1 = HistoryStatsSensor(
            self.hass, 'test', 'on', bad, None, good_duration, 'Test')
        sensor2 = HistoryStatsSensor(
            self.hass, 'test', 'on', None, bad, good_duration, 'Test')
        sensor3 = HistoryStatsSensor(
            self.hass, 'test', 'on', good, None, bad, 'Test')

        before_update1 = sensor1._period
        before_update2 = sensor2._period
        before_update3 = sensor3._period

        sensor1.update_period()
        sensor2.update_period()
        sensor3.update_period()

        self.assertEqual(before_update1, sensor1._period)
        self.assertEqual(before_update2, sensor2._period)
        self.assertEqual(before_update3, sensor3._period)

    def test_not_enough_arguments(self):
        """Test config when not enough arguments provided."""
        self.init_recorder()
        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_stats',
                'entity_id': 'binary_sensor.test_id',
                'name': 'Test',
                'state': 'on',
                'start': '{{ now() }}',
            }
        }

        setup_component(self.hass, 'sensor', config)
        self.assertEqual(self.hass.states.get('sensor.test'), None)
        self.assertRaises(TypeError,
                          setup_component(self.hass, 'sensor', config))

    def test_too_many_arguments(self):
        """Test config when too many arguments provided."""
        self.init_recorder()
        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_stats',
                'entity_id': 'binary_sensor.test_id',
                'name': 'Test',
                'state': 'on',
                'start': '{{ as_timestamp(now()) - 3600 }}',
                'end': '{{ now() }}',
                'duration': '{{ 3600 }}',
            }
        }

        setup_component(self.hass, 'sensor', config)
        self.assertEqual(self.hass.states.get('sensor.test'), None)
        self.assertRaises(TypeError,
                          setup_component(self.hass, 'sensor', config))

    def init_recorder(self):
        """Initialize the recorder."""
        db_uri = 'sqlite://'
        with patch('homeassistant.core.Config.path', return_value=db_uri):
            setup_component(self.hass, recorder.DOMAIN, {
                "recorder": {
                    "db_url": db_uri}})
        self.hass.start()
        recorder._INSTANCE.block_till_db_ready()
        self.hass.block_till_done()
        recorder._INSTANCE.block_till_done()
