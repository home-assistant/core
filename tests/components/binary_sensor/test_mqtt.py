"""The tests for the  MQTT binary sensor platform."""
import unittest

from datetime import timedelta, datetime
from unittest.mock import patch

import homeassistant.core as ha
from homeassistant.setup import setup_component
import homeassistant.components.binary_sensor as binary_sensor
import homeassistant.util.dt as dt_util

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNAVAILABLE

from tests.common import get_test_home_assistant, fire_mqtt_message
from tests.common import mock_component, mock_mqtt_component


class TestSensorMQTT(unittest.TestCase):
    """Test the MQTT sensor."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_setting_sensor_value_via_mqtt_message(self):
        """Test the setting of the value via MQTT."""
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'payload_on': 'ON',
                'payload_off': 'OFF',
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_OFF, state.state)

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_ON, state.state)

        fire_mqtt_message(self.hass, 'test-topic', 'OFF')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_OFF, state.state)

    @patch('homeassistant.core.dt_util.utcnow')
    def test_setting_sensor_value_expires(self, mock_utcnow):
        """Test the expiration of the value."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'payload_on': 'ON',
                'expire_after': '4',
                'force_update': True
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual('off', state.state)

        now = datetime(2018, 8, 20, 1, tzinfo=dt_util.UTC)
        mock_utcnow.return_value = now
        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()

        # Value was set correctly.
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual('on', state.state)

        # Time jump +3s
        now = now + timedelta(seconds=3)
        self._send_time_changed(now)
        self.hass.block_till_done()

        # Value is not yet expired
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual('on', state.state)

        # Next message resets timer
        mock_utcnow.return_value = now
        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()

        # Value was updated correctly.
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual('on', state.state)

        # Time jump +3s
        now = now + timedelta(seconds=3)
        self._send_time_changed(now)
        self.hass.block_till_done()

        # Value is not yet expired
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual('on', state.state)

        # Time jump +2s
        now = now + timedelta(seconds=2)
        self._send_time_changed(now)
        self.hass.block_till_done()

        # Value is expired now
        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual('off', state.state)

    def test_valid_device_class(self):
        """Test the setting of a valid sensor class."""
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'device_class': 'motion',
                'state_topic': 'test-topic',
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual('motion', state.attributes.get('device_class'))

    def test_invalid_device_class(self):
        """Test the setting of an invalid sensor class."""
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'device_class': 'abc123',
                'state_topic': 'test-topic',
            }
        })

        state = self.hass.states.get('binary_sensor.test')
        self.assertIsNone(state)

    def test_unique_id(self):
        """Test unique id option only creates one sensor per unique_id."""
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: [{
                'platform': 'mqtt',
                'name': 'Test 1',
                'state_topic': 'test-topic',
                'unique_id': 'TOTALLY_UNIQUE'
            }, {
                'platform': 'mqtt',
                'name': 'Test 2',
                'state_topic': 'test-topic',
                'unique_id': 'TOTALLY_UNIQUE'
            }]
        })
        fire_mqtt_message(self.hass, 'test-topic', 'payload')
        self.hass.block_till_done()
        assert len(self.hass.states.all()) == 1

    def test_availability_without_topic(self):
        """Test availability without defined availability topic."""
        self.assertTrue(setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
            }
        }))

        state = self.hass.states.get('binary_sensor.test')
        self.assertNotEqual(STATE_UNAVAILABLE, state.state)

    def test_availability_by_defaults(self):
        """Test availability by defaults with defined topic."""
        self.assertTrue(setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'availability_topic': 'availability-topic'
            }
        }))

        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'online')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test')
        self.assertNotEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'offline')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

    def test_availability_by_custom_payload(self):
        """Test availability by custom payload with defined topic."""
        self.assertTrue(setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'availability_topic': 'availability-topic',
                'payload_available': 'good',
                'payload_not_available': 'nogood'
            }
        }))

        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'good')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test')
        self.assertNotEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'nogood')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

    def test_force_update_disabled(self):
        """Test force update option."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'payload_on': 'ON',
                'payload_off': 'OFF'
            }
        })

        events = []

        @ha.callback
        def callback(event):
            """Verify event got called."""
            events.append(event)

        self.hass.bus.listen(EVENT_STATE_CHANGED, callback)

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()
        self.assertEqual(1, len(events))

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()
        self.assertEqual(1, len(events))

    def test_force_update_enabled(self):
        """Test force update option."""
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, binary_sensor.DOMAIN, {
            binary_sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'payload_on': 'ON',
                'payload_off': 'OFF',
                'force_update': True
            }
        })

        events = []

        @ha.callback
        def callback(event):
            """Verify event got called."""
            events.append(event)

        self.hass.bus.listen(EVENT_STATE_CHANGED, callback)

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()
        self.assertEqual(1, len(events))

        fire_mqtt_message(self.hass, 'test-topic', 'ON')
        self.hass.block_till_done()
        self.assertEqual(2, len(events))

    def _send_time_changed(self, now):
        """Send a time changed event."""
        self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: now})
