"""The tests for the MQTT sensor platform."""
import unittest

from homeassistant.bootstrap import _setup_component
import homeassistant.components.sensor as sensor
from tests.common import mock_mqtt_component, fire_mqtt_message

from tests.common import get_test_home_assistant


class TestSensorMQTT(unittest.TestCase):
    """Test the MQTT sensor."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setting_sensor_value_via_mqtt_message(self):
        """Test the setting of the value via MQTT."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'unit_of_measurement': 'fav unit'
            }
        })

        fire_mqtt_message(self.hass, 'test-topic', '100')
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test')

        self.assertEqual('100', state.state)
        self.assertEqual('fav unit',
                         state.attributes.get('unit_of_measurement'))

    def test_setting_sensor_value_via_mqtt_json_message(self):
        """Test the setting of the value via MQTT with JSON playload."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test-topic',
                'unit_of_measurement': 'fav unit',
                'value_template': '{{ value_json.val }}'
            }
        })

        fire_mqtt_message(self.hass, 'test-topic', '{ "val": "100" }')
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test')

        self.assertEqual('100', state.state)
