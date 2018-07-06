"""The tests for the mqtt climate component."""
import unittest
import copy

from homeassistant.util.unit_system import (
    METRIC_SYSTEM
)
from homeassistant.setup import setup_component
from homeassistant.components import climate
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.components.climate import (
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE, SUPPORT_SWING_MODE, SUPPORT_HOLD_MODE,
    SUPPORT_AWAY_MODE, SUPPORT_AUX_HEAT, DEFAULT_MIN_TEMP, DEFAULT_MAX_TEMP)
from tests.common import (get_test_home_assistant, mock_mqtt_component,
                          fire_mqtt_message, mock_component)

ENTITY_CLIMATE = 'climate.test'

DEFAULT_CONFIG = {
    'climate': {
        'platform': 'mqtt',
        'name': 'test',
        'mode_command_topic': 'mode-topic',
        'temperature_command_topic': 'temperature-topic',
        'fan_mode_command_topic': 'fan-mode-topic',
        'swing_mode_command_topic': 'swing-mode-topic',
        'away_mode_command_topic': 'away-mode-topic',
        'hold_command_topic': 'hold-topic',
        'aux_command_topic': 'aux-topic'
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
        self.assertEqual(DEFAULT_MIN_TEMP, state.attributes.get('min_temp'))
        self.assertEqual(DEFAULT_MAX_TEMP, state.attributes.get('max_temp'))

    def test_supported_features(self):
        """Test the supported_features."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        support = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
                   SUPPORT_SWING_MODE | SUPPORT_FAN_MODE | SUPPORT_AWAY_MODE |
                   SUPPORT_HOLD_MODE | SUPPORT_AUX_HEAT)

        self.assertEqual(state.attributes.get("supported_features"), support)

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
        self.mock_publish.async_publish.assert_called_once_with(
            'mode-topic', 'cool', 0, False)

    def test_set_operation_pessimistic(self):
        """Test setting operation mode in pessimistic mode."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['mode_state_topic'] = 'mode-state'
        assert setup_component(self.hass, climate.DOMAIN, config)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('operation_mode'))
        self.assertEqual("off", state.state)

        climate.set_operation_mode(self.hass, "cool", ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('operation_mode'))
        self.assertEqual("off", state.state)

        fire_mqtt_message(self.hass, 'mode-state', 'cool')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("cool", state.attributes.get('operation_mode'))
        self.assertEqual("cool", state.state)

        fire_mqtt_message(self.hass, 'mode-state', 'bogus mode')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("cool", state.attributes.get('operation_mode'))
        self.assertEqual("cool", state.state)

    def test_set_operation_with_power_command(self):
        """Test setting of new operation mode with power command enabled."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['power_command_topic'] = 'power-command'
        assert setup_component(self.hass, climate.DOMAIN, config)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('operation_mode'))
        self.assertEqual("off", state.state)
        climate.set_operation_mode(self.hass, "on", ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("on", state.attributes.get('operation_mode'))
        self.assertEqual("on", state.state)
        self.mock_publish.async_publish.assert_has_calls([
            unittest.mock.call('power-command', 'ON', 0, False),
            unittest.mock.call('mode-topic', 'on', 0, False)
        ])
        self.mock_publish.async_publish.reset_mock()

        climate.set_operation_mode(self.hass, "off", ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('operation_mode'))
        self.assertEqual("off", state.state)
        self.mock_publish.async_publish.assert_has_calls([
            unittest.mock.call('power-command', 'OFF', 0, False),
            unittest.mock.call('mode-topic', 'off', 0, False)
        ])
        self.mock_publish.async_publish.reset_mock()

    def test_set_fan_mode_bad_attr(self):
        """Test setting fan mode without required attribute."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("low", state.attributes.get('fan_mode'))
        climate.set_fan_mode(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("low", state.attributes.get('fan_mode'))

    def test_set_fan_mode_pessimistic(self):
        """Test setting of new fan mode in pessimistic mode."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['fan_mode_state_topic'] = 'fan-state'
        assert setup_component(self.hass, climate.DOMAIN, config)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("low", state.attributes.get('fan_mode'))

        climate.set_fan_mode(self.hass, 'high', ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("low", state.attributes.get('fan_mode'))

        fire_mqtt_message(self.hass, 'fan-state', 'high')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('high', state.attributes.get('fan_mode'))

        fire_mqtt_message(self.hass, 'fan-state', 'bogus mode')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('high', state.attributes.get('fan_mode'))

    def test_set_fan_mode(self):
        """Test setting of new fan mode."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("low", state.attributes.get('fan_mode'))
        climate.set_fan_mode(self.hass, 'high', ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            'fan-mode-topic', 'high', 0, False)
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

    def test_set_swing_pessimistic(self):
        """Test setting swing mode in pessimistic mode."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['swing_mode_state_topic'] = 'swing-state'
        assert setup_component(self.hass, climate.DOMAIN, config)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('swing_mode'))

        climate.set_swing_mode(self.hass, 'on', ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('swing_mode'))

        fire_mqtt_message(self.hass, 'swing-state', 'on')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("on", state.attributes.get('swing_mode'))

        fire_mqtt_message(self.hass, 'swing-state', 'bogus state')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("on", state.attributes.get('swing_mode'))

    def test_set_swing(self):
        """Test setting of new swing mode."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('swing_mode'))
        climate.set_swing_mode(self.hass, 'on', ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            'swing-mode-topic', 'on', 0, False)
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("on", state.attributes.get('swing_mode'))

    def test_set_target_temperature(self):
        """Test setting the target temperature."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(21, state.attributes.get('temperature'))
        climate.set_operation_mode(self.hass, 'heat', ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('heat', state.attributes.get('operation_mode'))
        self.mock_publish.async_publish.assert_called_once_with(
            'mode-topic', 'heat', 0, False)
        self.mock_publish.async_publish.reset_mock()
        climate.set_temperature(self.hass, temperature=47,
                                entity_id=ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(47, state.attributes.get('temperature'))
        self.mock_publish.async_publish.assert_called_once_with(
            'temperature-topic', 47, 0, False)

        # also test directly supplying the operation mode to set_temperature
        self.mock_publish.async_publish.reset_mock()
        climate.set_temperature(self.hass, temperature=21,
                                operation_mode="cool",
                                entity_id=ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('cool', state.attributes.get('operation_mode'))
        self.assertEqual(21, state.attributes.get('temperature'))
        self.mock_publish.async_publish.assert_has_calls([
            unittest.mock.call('mode-topic', 'cool', 0, False),
            unittest.mock.call('temperature-topic', 21, 0, False)
        ])
        self.mock_publish.async_publish.reset_mock()

    def test_set_target_temperature_pessimistic(self):
        """Test setting the target temperature."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['temperature_state_topic'] = 'temperature-state'
        assert setup_component(self.hass, climate.DOMAIN, config)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(21, state.attributes.get('temperature'))
        climate.set_operation_mode(self.hass, 'heat', ENTITY_CLIMATE)
        self.hass.block_till_done()
        climate.set_temperature(self.hass, temperature=47,
                                entity_id=ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(21, state.attributes.get('temperature'))

        fire_mqtt_message(self.hass, 'temperature-state', '1701')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(1701, state.attributes.get('temperature'))

        fire_mqtt_message(self.hass, 'temperature-state', 'not a number')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(1701, state.attributes.get('temperature'))

    def test_receive_mqtt_temperature(self):
        """Test getting the current temperature via MQTT."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['current_temperature_topic'] = 'current_temperature'
        mock_component(self.hass, 'mqtt')
        assert setup_component(self.hass, climate.DOMAIN, config)

        fire_mqtt_message(self.hass, 'current_temperature', '47')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(47, state.attributes.get('current_temperature'))

    def test_set_away_mode_pessimistic(self):
        """Test setting of the away mode."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['away_mode_state_topic'] = 'away-state'
        assert setup_component(self.hass, climate.DOMAIN, config)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('away_mode'))

        climate.set_away_mode(self.hass, True, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('away_mode'))

        fire_mqtt_message(self.hass, 'away-state', 'ON')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('on', state.attributes.get('away_mode'))

        fire_mqtt_message(self.hass, 'away-state', 'OFF')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('away_mode'))

        fire_mqtt_message(self.hass, 'away-state', 'nonsense')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('away_mode'))

    def test_set_away_mode(self):
        """Test setting of the away mode."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['payload_on'] = 'AN'
        config['climate']['payload_off'] = 'AUS'

        assert setup_component(self.hass, climate.DOMAIN, config)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('away_mode'))
        climate.set_away_mode(self.hass, True, ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            'away-mode-topic', 'AN', 0, False)
        self.mock_publish.async_publish.reset_mock()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('on', state.attributes.get('away_mode'))

        climate.set_away_mode(self.hass, False, ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            'away-mode-topic', 'AUS', 0, False)
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('away_mode'))

    def test_set_hold_pessimistic(self):
        """Test setting the hold mode in pessimistic mode."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['hold_state_topic'] = 'hold-state'
        assert setup_component(self.hass, climate.DOMAIN, config)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(None, state.attributes.get('hold_mode'))

        climate.set_hold_mode(self.hass, 'on', ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(None, state.attributes.get('hold_mode'))

        fire_mqtt_message(self.hass, 'hold-state', 'on')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('on', state.attributes.get('hold_mode'))

        fire_mqtt_message(self.hass, 'hold-state', 'off')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('hold_mode'))

    def test_set_hold(self):
        """Test setting the hold mode."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(None, state.attributes.get('hold_mode'))
        climate.set_hold_mode(self.hass, 'on', ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            'hold-topic', 'on', 0, False)
        self.mock_publish.async_publish.reset_mock()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('on', state.attributes.get('hold_mode'))

        climate.set_hold_mode(self.hass, 'off', ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            'hold-topic', 'off', 0, False)
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('hold_mode'))

    def test_set_aux_pessimistic(self):
        """Test setting of the aux heating in pessimistic mode."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['aux_state_topic'] = 'aux-state'
        assert setup_component(self.hass, climate.DOMAIN, config)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('aux_heat'))

        climate.set_aux_heat(self.hass, True, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('aux_heat'))

        fire_mqtt_message(self.hass, 'aux-state', 'ON')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('on', state.attributes.get('aux_heat'))

        fire_mqtt_message(self.hass, 'aux-state', 'OFF')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('aux_heat'))

        fire_mqtt_message(self.hass, 'aux-state', 'nonsense')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('aux_heat'))

    def test_set_aux(self):
        """Test setting of the aux heating."""
        assert setup_component(self.hass, climate.DOMAIN, DEFAULT_CONFIG)

        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('aux_heat'))
        climate.set_aux_heat(self.hass, True, ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            'aux-topic', 'ON', 0, False)
        self.mock_publish.async_publish.reset_mock()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('on', state.attributes.get('aux_heat'))

        climate.set_aux_heat(self.hass, False, ENTITY_CLIMATE)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            'aux-topic', 'OFF', 0, False)
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('aux_heat'))

    def test_custom_availability_payload(self):
        """Test availability by custom payload with defined topic."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['availability_topic'] = 'availability-topic'
        config['climate']['payload_available'] = 'good'
        config['climate']['payload_not_available'] = 'nogood'

        assert setup_component(self.hass, climate.DOMAIN, config)

        state = self.hass.states.get('climate.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'good')
        self.hass.block_till_done()

        state = self.hass.states.get('climate.test')
        self.assertNotEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'nogood')
        self.hass.block_till_done()

        state = self.hass.states.get('climate.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

    def test_set_with_templates(self):
        """Test setting of new fan mode in pessimistic mode."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        # By default, just unquote the JSON-strings
        config['climate']['value_template'] = '{{ value_json }}'
        # Something more complicated for hold mode
        config['climate']['hold_state_template'] = \
            '{{ value_json.attribute }}'
        # Rendering to a bool for aux heat
        config['climate']['aux_state_template'] = \
            "{{ value == 'switchmeon' }}"

        config['climate']['mode_state_topic'] = 'mode-state'
        config['climate']['fan_mode_state_topic'] = 'fan-state'
        config['climate']['swing_mode_state_topic'] = 'swing-state'
        config['climate']['temperature_state_topic'] = 'temperature-state'
        config['climate']['away_mode_state_topic'] = 'away-state'
        config['climate']['hold_state_topic'] = 'hold-state'
        config['climate']['aux_state_topic'] = 'aux-state'
        config['climate']['current_temperature_topic'] = 'current-temperature'

        assert setup_component(self.hass, climate.DOMAIN, config)

        # Operation Mode
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("off", state.attributes.get('operation_mode'))
        fire_mqtt_message(self.hass, 'mode-state', '"cool"')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("cool", state.attributes.get('operation_mode'))

        # Fan Mode
        self.assertEqual("low", state.attributes.get('fan_mode'))
        fire_mqtt_message(self.hass, 'fan-state', '"high"')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('high', state.attributes.get('fan_mode'))

        # Swing Mode
        self.assertEqual("off", state.attributes.get('swing_mode'))
        fire_mqtt_message(self.hass, 'swing-state', '"on"')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual("on", state.attributes.get('swing_mode'))

        # Temperature - with valid value
        self.assertEqual(21, state.attributes.get('temperature'))
        fire_mqtt_message(self.hass, 'temperature-state', '"1031"')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(1031, state.attributes.get('temperature'))

        # Temperature - with invalid value
        with self.assertLogs(level='ERROR') as log:
            fire_mqtt_message(self.hass, 'temperature-state', '"-INVALID-"')
            self.hass.block_till_done()
            state = self.hass.states.get(ENTITY_CLIMATE)
            # make sure, the invalid value gets logged...
            self.assertEqual(len(log.output), 1)
            self.assertEqual(len(log.records), 1)
            self.assertIn(
                "Could not parse temperature from -INVALID-",
                log.output[0]
            )
            # ... but the actual value stays unchanged.
            self.assertEqual(1031, state.attributes.get('temperature'))

        # Away Mode
        self.assertEqual('off', state.attributes.get('away_mode'))
        fire_mqtt_message(self.hass, 'away-state', '"ON"')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('on', state.attributes.get('away_mode'))

        # Away Mode with JSON values
        fire_mqtt_message(self.hass, 'away-state', 'false')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('away_mode'))

        fire_mqtt_message(self.hass, 'away-state', 'true')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('on', state.attributes.get('away_mode'))

        # Hold Mode
        self.assertEqual(None, state.attributes.get('hold_mode'))
        fire_mqtt_message(self.hass, 'hold-state', """
            { "attribute": "somemode" }
        """)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('somemode', state.attributes.get('hold_mode'))

        # Aux mode
        self.assertEqual('off', state.attributes.get('aux_heat'))
        fire_mqtt_message(self.hass, 'aux-state', 'switchmeon')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('on', state.attributes.get('aux_heat'))

        # anything other than 'switchmeon' should turn Aux mode off
        fire_mqtt_message(self.hass, 'aux-state', 'somerandomstring')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual('off', state.attributes.get('aux_heat'))

        # Current temperature
        fire_mqtt_message(self.hass, 'current-temperature', '"74656"')
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        self.assertEqual(74656, state.attributes.get('current_temperature'))

    def test_min_temp_custom(self):
        """Test a custom min temp."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['min_temp'] = 26

        assert setup_component(self.hass, climate.DOMAIN, config)

        state = self.hass.states.get(ENTITY_CLIMATE)
        min_temp = state.attributes.get('min_temp')

        self.assertIsInstance(min_temp, float)
        self.assertEqual(26, state.attributes.get('min_temp'))

    def test_max_temp_custom(self):
        """Test a custom max temp."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config['climate']['max_temp'] = 60

        assert setup_component(self.hass, climate.DOMAIN, config)

        state = self.hass.states.get(ENTITY_CLIMATE)
        max_temp = state.attributes.get('max_temp')

        self.assertIsInstance(max_temp, float)
        self.assertEqual(60, max_temp)
