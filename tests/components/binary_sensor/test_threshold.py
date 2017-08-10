"""The test for the threshold sensor platform."""
import unittest
from unittest.mock import patch
from datetime import timedelta

from homeassistant.setup import setup_component
from homeassistant.const import (ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS)
import homeassistant.util.dt as dt_util

from tests.common import (get_test_home_assistant, fire_time_changed)


class TestThresholdSensor(unittest.TestCase):
    """Test the threshold sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_sensor_upper(self):
        """Test if source is above threshold."""
        config = {
            'binary_sensor': {
                'platform': 'threshold',
                'threshold': '15',
                'type': 'upper',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 16,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        self.assertEqual('upper', state.attributes.get('type'))
        self.assertEqual('sensor.test_monitored',
                         state.attributes.get('entity_id'))
        self.assertEqual(16, state.attributes.get('sensor_value'))
        self.assertEqual(float(config['binary_sensor']['threshold']),
                         state.attributes.get('threshold'))

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 14)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 15)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.threshold')

        assert state.state == 'off'

    def test_sensor_lower(self):
        """Test if source is below threshold."""
        config = {
            'binary_sensor': {
                'platform': 'threshold',
                'threshold': '15',
                'name': 'Test_threshold',
                'type': 'lower',
                'entity_id': 'sensor.test_monitored',
            }
        }

        assert setup_component(self.hass, 'binary_sensor', config)

        self.hass.states.set('sensor.test_monitored', 16)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_threshold')

        self.assertEqual('lower', state.attributes.get('type'))

        assert state.state == 'off'

        self.hass.states.set('sensor.test_monitored', 14)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_threshold')

        assert state.state == 'on'

        self.hass.states.set('sensor.test_monitored', 15)
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_threshold')

        assert state.state == 'off'

    def test_sensor_with_on_delay(self):
        """Test if source is below threshold."""
        now = dt_util.utcnow()
        with patch('homeassistant.core.dt_util.utcnow') as mock_utcnow:
            mock_utcnow.return_value = now

            config = {
                'binary_sensor': {
                    'platform': 'threshold',
                    'threshold': '15',
                    'name': 'Test_threshold',
                    'type': 'lower',
                    'entity_id': 'sensor.test_monitored',
                    'on_delay': {
                        'seconds': 10
                    }
                }
            }

            assert setup_component(self.hass, 'binary_sensor', config)

            self.hass.states.set('sensor.test_monitored', 16)
            self.hass.block_till_done()

            state = self.hass.states.get('binary_sensor.test_threshold')
            assert state.state == 'off'

            self.hass.states.set('sensor.test_monitored', 14)
            self.hass.block_till_done()

            # state is still off, because the delay has not been met
            state = self.hass.states.get('binary_sensor.test_threshold')
            assert state.state == 'off'

            now += timedelta(seconds=5)
            mock_utcnow.return_value = now
            fire_time_changed(self.hass, now)
            self.hass.block_till_done()

            # state is still off, because the delay has still not been met
            state = self.hass.states.get('binary_sensor.test_threshold')
            assert state.state == 'off'

            self.hass.states.set('sensor.test_monitored', 16)
            self.hass.block_till_done()

            now += timedelta(seconds=10)
            mock_utcnow.return_value = now
            fire_time_changed(self.hass, now)
            self.hass.block_till_done()

            # enough time passed, but the threshold switched back before then,
            # so state should still be off
            state = self.hass.states.get('binary_sensor.test_threshold')
            assert state.state == 'off'

            self.hass.states.set('sensor.test_monitored', 14)
            self.hass.block_till_done()

            now += timedelta(seconds=20)
            mock_utcnow.return_value = now
            fire_time_changed(self.hass, now)
            self.hass.block_till_done()

            # enough time passed for state to switch to on!
            state = self.hass.states.get('binary_sensor.test_threshold')
            assert state.state == 'on'

    def test_sensor_with_off_delay(self):
        """Test if source is below threshold."""
        now = dt_util.utcnow()
        with patch('homeassistant.core.dt_util.utcnow') as mock_utcnow:
            mock_utcnow.return_value = now

            config = {
                'binary_sensor': {
                    'platform': 'threshold',
                    'threshold': '15',
                    'name': 'Test_threshold',
                    'type': 'lower',
                    'entity_id': 'sensor.test_monitored',
                    'off_delay': {
                        'seconds': 10
                    }
                }
            }

            assert setup_component(self.hass, 'binary_sensor', config)

            self.hass.states.set('sensor.test_monitored', 14)
            self.hass.block_till_done()

            state = self.hass.states.get('binary_sensor.test_threshold')
            assert state.state == 'on'

            self.hass.states.set('sensor.test_monitored', 16)
            self.hass.block_till_done()

            # state is still on, because the delay has not been met
            state = self.hass.states.get('binary_sensor.test_threshold')
            assert state.state == 'on'

            now += timedelta(seconds=5)
            mock_utcnow.return_value = now
            fire_time_changed(self.hass, now)
            self.hass.block_till_done()

            # state is still on, because the delay has still not been met
            state = self.hass.states.get('binary_sensor.test_threshold')
            assert state.state == 'on'

            self.hass.states.set('sensor.test_monitored', 14)
            self.hass.block_till_done()

            now += timedelta(seconds=10)
            mock_utcnow.return_value = now
            fire_time_changed(self.hass, now)
            self.hass.block_till_done()

            # enough time passed, but the threshold switched back before then,
            # so state should still be on
            state = self.hass.states.get('binary_sensor.test_threshold')
            assert state.state == 'on'

            self.hass.states.set('sensor.test_monitored', 16)
            self.hass.block_till_done()

            now += timedelta(seconds=20)
            mock_utcnow.return_value = now
            fire_time_changed(self.hass, now)
            self.hass.block_till_done()

            # enough time passed for state to switch to on!
            state = self.hass.states.get('binary_sensor.test_threshold')
            assert state.state == 'off'

    def test_sensor_with_both_delays(self):
        """Test if source is below threshold."""
        now = dt_util.utcnow()
        with patch('homeassistant.core.dt_util.utcnow') as mock_utcnow:
            mock_utcnow.return_value = now

            config = {
                'binary_sensor': {
                    'platform': 'threshold',
                    'threshold': '15',
                    'name': 'Test_threshold',
                    'type': 'lower',
                    'entity_id': 'sensor.test_monitored',
                    'on_delay': {
                        'seconds': 10
                    },
                    'off_delay': {
                        'seconds': 10
                    }
                }
            }

            assert setup_component(self.hass, 'binary_sensor', config)

            self.hass.states.set('sensor.test_monitored', 16)
            self.hass.block_till_done()

            # State defaults to off when initialized
            state = self.hass.states.get('binary_sensor.test_threshold')
            self.assertEqual(16, state.attributes.get('sensor_value'))
            assert state.state == 'off'

            self.hass.states.set('sensor.test_monitored', 14)
            self.hass.block_till_done()

            now += timedelta(seconds=5)
            mock_utcnow.return_value = now
            fire_time_changed(self.hass, now)
            self.hass.block_till_done()

            # state is still off, because on_delay has not been met
            state = self.hass.states.get('binary_sensor.test_threshold')
            self.assertEqual(14, state.attributes.get('sensor_value'))
            assert state.state == 'off'

            self.hass.states.set('sensor.test_monitored', 16)
            self.hass.block_till_done()

            now += timedelta(seconds=6)
            mock_utcnow.return_value = now
            fire_time_changed(self.hass, now)
            self.hass.block_till_done()

            # on_delay passed, but threshold swapped back,
            # so state is still off
            state = self.hass.states.get('binary_sensor.test_threshold')
            self.assertEqual(16, state.attributes.get('sensor_value'))
            assert state.state == 'off'

            now += timedelta(seconds=11)
            mock_utcnow.return_value = now
            fire_time_changed(self.hass, now)
            self.hass.block_till_done()

            # now off_delay has passed, and nothing should have changed
            state = self.hass.states.get('binary_sensor.test_threshold')
            assert state.state == 'off'

            self.hass.states.set('sensor.test_monitored', 14)
            self.hass.block_till_done()

            now += timedelta(seconds=11)
            mock_utcnow.return_value = now
            fire_time_changed(self.hass, now)
            self.hass.block_till_done()

            # on_delay has passed - state should swap to on
            state = self.hass.states.get('binary_sensor.test_threshold')
            assert state.state == 'on'

            self.hass.states.set('sensor.test_monitored', 16)
            self.hass.block_till_done()

            now += timedelta(seconds=5)
            mock_utcnow.return_value = now
            fire_time_changed(self.hass, now)
            self.hass.block_till_done()

            # waiting for off_delay, so state is still on
            state = self.hass.states.get('binary_sensor.test_threshold')
            self.assertEqual(16, state.attributes.get('sensor_value'))
            assert state.state == 'on'

            now += timedelta(seconds=6)
            mock_utcnow.return_value = now
            fire_time_changed(self.hass, now)
            self.hass.block_till_done()

            # off_delay has passed, state swapped back to off
            state = self.hass.states.get('binary_sensor.test_threshold')
            assert state.state == 'off'
