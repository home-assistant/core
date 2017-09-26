"""The tests for the mqtt climate component."""
import unittest
import copy

from homeassistant.util.unit_system import (
    METRIC_SYSTEM
)
from homeassistant.setup import setup_component
from homeassistant.components import climate
from homeassistant.const import (STATE_OFF, ATTR_UNIT_OF_MEASUREMENT,
                                 TEMP_CELSIUS)

from tests.common import (get_test_home_assistant, mock_mqtt_component,
                          fire_mqtt_message, mock_component)

ENTITY_CLIMATE = 'climate.test'
ENT_SENSOR = 'sensor.test'

DEFAULT_CONFIG = {
    'climate': {
        'platform': 'mqtt',
        'name': 'test',
        'target_sensor': ENT_SENSOR,
        'mode_command_topic': 'mode-topic',
        'temperature_command_topic': 'temperature-topic',
        'fan_mode_command_topic': 'fan-mode-topic',
        'swing_mode_command_topic': 'swing-mode-topic',
    }}


class TestMQTTClimate(unittest.TestCase):
    """Test the mqtt climate hvac."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)
        self.hass.config.units = METRIC_SYSTEM

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_params(self):
        """Test the initial parameters."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(21, state.attributes.get('temperature'))
        self.assertEqual("low", state.attributes.get('fan_mode'))
        self.assertEqual("off", state.attributes.get('swing_mode'))
        self.assertEqual("off", state.attributes.get('operation_mode'))

    def test_get_operation_modes(self):
        """Test that the operation list returns the correct modes."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        modes = state.attributes.get('operation_list')
        self.assertEqual([
            climate.STATE_AUTO, STATE_OFF, climate.STATE_COOL,
            climate.STATE_HEAT, climate.STATE_DRY, climate.STATE_FAN_ONLY
        ], modes)

    def test_set_operation_bad_attr_and_state(self):
        """Test setting operation mode without required attribute.

        Also check the state.
        """
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('operation_mode'))
        self.assertEqual("off", state.state)
        climate.set_operation_mode(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('operation_mode'))
        self.assertEqual("off", state.state)

    def test_set_operation(self):
        """Test setting of new operation mode."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('operation_mode'))
        self.assertEqual("off", state.state)
        climate.set_operation_mode(self.hass, "cool", ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("cool", state.attributes.get('operation_mode'))
        self.assertEqual("cool", state.state)
        self.assertEqual(('mode-topic', 'cool', 0, False),
                         self.mock_publish.mock_calls[-2][1])

    def test_set_fan_mode_bad_attr(self):
        """Test setting fan mode without required attribute."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("low", state.attributes.get('fan_mode'))
        climate.set_fan_mode(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("low", state.attributes.get('fan_mode'))

    def test_set_fan_mode(self):
        """Test setting of new fan mode."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("low", state.attributes.get('fan_mode'))
        climate.set_fan_mode(self.hass, 'high', ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.assertEqual(('fan-mode-topic', 'high', 0, False),
                         self.mock_publish.mock_calls[-2][1])
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('high', state.attributes.get('fan_mode'))

    def test_set_swing_mode_bad_attr(self):
        """Test setting swing mode without required attribute."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('swing_mode'))
        climate.set_swing_mode(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('swing_mode'))

    def test_set_swing(self):
        """Test setting of new swing mode."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('swing_mode'))
        climate.set_swing_mode(self.hass, 'on', ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.assertEqual(('swing-mode-topic', 'on', 0, False),
                         self.mock_publish.mock_calls[-2][1])
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("on", state.attributes.get('swing_mode'))

    def test_set_target_temperature(self):
        """Test setting the target temperature."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(21, state.attributes.get('temperature'))
        climate.set_operation_mode(self.hass, 'heat', ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.assertEqual(('mode-topic', 'heat', 0, False),
                         self.mock_publish.mock_calls[-2][1])
        climate.set_temperature(self.hass, temperature=47,
                                entity_id=ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(47, state.attributes.get('temperature'))
        self.assertEqual(('temperature-topic', 47, 0, False),
                         self.mock_publish.mock_calls[-2][1])

    def test_sensor_changed(self):
        """Test getting the temperature from a changing sensor."""
        self.hass.states.set(ENT_SENSOR, 0,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(0, state.attributes.get('current_temperature'))

        self.hass.states.set(ENT_SENSOR, 42,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(42, state.attributes.get('current_temperature'))

    def test_receive_mqtt_temperature(self):
        """Test getting the current temperature via MQTT."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['current_temperature_topic'] = 'current_temperature'
        del config['climate']['target_sensor']
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, climate.DOMAIN, config)

        fire_mqtt_message(self.hass, 'current_temperature', '47')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(47, state.attributes.get('current_temperature'))
