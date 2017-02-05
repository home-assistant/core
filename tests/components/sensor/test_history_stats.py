"""The test for the History Statistics sensor platform."""
# pylint: disable=protected-access
import unittest
from datetime import timedelta
from unittest.mock import patch

import homeassistant.components.recorder as recorder
import homeassistant.core as ha
import homeassistant.util.dt as dt_util
from homeassistant.bootstrap import setup_component
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
                         + '.replace(minute=0).replace(second=0) }}',
                'duration': '{{ 3600 * 2 + 60 }}',
                'name': 'Test',
            }
        }

        self.assertTrue(setup_component(self.hass, 'sensor', config))

        state = self.hass.states.get('sensor.test').as_dict()

        self.assertEqual(state['state'], '0')
        self.assertEqual(state['attributes']['from'][-8:], '00:00:00')
        self.assertEqual(state['attributes']['to'][-8:], '02:01:00')

    def test_measure(self):
        """Test the history statistics sensor measure."""
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
            }
        }

        later = dt_util.utcnow() - timedelta(seconds=15)
        earlier = later - timedelta(minutes=30)

        fake_states = {
            'binary_sensor.test_id': [
                ha.State('binary_sensor.test_id', 'on', last_changed=earlier),
                ha.State('binary_sensor.test_id', 'off', last_changed=later),
            ]
        }

        with patch('homeassistant.components.history.'
                   'state_changes_during_period', return_value=fake_states):
            assert setup_component(self.hass, 'sensor', config)

        state = self.hass.states.get('sensor.test').as_dict()
        self.assertEqual(state['state'], '0.5')
        self.assertEqual(state['attributes']['ratio'], '50.0%')

    def test_wrong_start(self):
        """Test Exception when start value is not a timestamp or a date."""
        self.init_recorder()
        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_stats',
                'entity_id': 'binary_sensor.test_id',
                'name': 'Test',
                'state': 'on',
                'start': '{{ TEST }}',
                'end': '{{ now() }}',
            }
        }

        self.assertRaises(TypeError,
                          setup_component(self.hass, 'sensor', config))

    def test_wrong_end(self):
        """Test Exception when end value is not a timestamp or a date."""
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
                'end': '{{ TEST }}',
            }
        }

        self.assertRaises(TypeError,
                          setup_component(self.hass, 'sensor', config))

    def test_wrong_duration(self):
        """Test Exception when duration value is not a number."""
        self.init_recorder()

        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_stats',
                'entity_id': 'binary_sensor.test_id',
                'name': 'Test',
                'state': 'on',
                'start': '{{ as_timestamp(now()) - 24 * 3600 }}',
                'duration': '{{ now() }}',
            }
        }

        self.assertRaises(TypeError,
                          setup_component(self.hass, 'sensor', config))

    def test_bad_template(self):
        """Test Exception when the template cannot be parsed."""
        self.init_recorder()
        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_stats',
                'entity_id': 'binary_sensor.test_id',
                'name': 'Test',
                'state': 'on',
                'end': '{{ x - 12 }}',  # <= x in undefined
                'duration': '{{ 3600 }}',
            }
        }

        self.assertRaises(TypeError,
                          setup_component(self.hass, 'sensor', config))

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

    def test_no_recorder(self):
        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_stats',
                'entity_id': 'binary_sensor.test_id',
                'state': 'on',
                'start': '{{ now().replace(hour=0)'
                         + '.replace(minute=0).replace(second=0) }}',
                'duration': '{{ 3600 * 2 + 60 }}',
                'name': 'Test',
            }
        }

        with patch('homeassistant.components.recorder.Recorder.'
                   '_setup_connection', return_value=False):
            self.assertRaises(Exception,
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
