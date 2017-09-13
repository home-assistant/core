"""The tests for the Demo vacuum platform."""
import unittest

from homeassistant.components import vacuum
from homeassistant.components.vacuum import (
    ATTR_BATTERY_LEVEL, services_to_strings, ATTR_BATTERY_ICON, ATTR_STATUS,
    ATTR_FAN_SPEED)
from homeassistant.components.vacuum.mqtt import ALL_SERVICES, \
    CONF_BATTERY_LEVEL_TOPIC, CONF_BATTERY_LEVEL_TEMPLATE
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES, CONF_PLATFORM, STATE_OFF, STATE_ON, CONF_NAME)
from homeassistant.setup import setup_component
from tests.common import (
    fire_mqtt_message, get_test_home_assistant, mock_mqtt_component)


class TestVacuumMQTT(unittest.TestCase):
    """MQTT vacuum component test class."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_default_supported_features(self):
        """Test that the correct supported features."""
        self.assertTrue(setup_component(self.hass, vacuum.DOMAIN, {
            vacuum.DOMAIN: {
                CONF_PLATFORM: 'mqtt',
                CONF_NAME: 'mqtttest',
            }
        }))
        entity = self.hass.states.get('vacuum.mqtttest')
        entity_features = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        self.assertListEqual(sorted(services_to_strings(entity_features)),
                             sorted(['turn_on', 'turn_off', 'stop',
                                     'return_home', 'battery', 'status',
                                     'clean_spot']))

    def test_all_commands(self):
        """Test simple commands to the vacuum."""
        self.assertTrue(setup_component(self.hass, vacuum.DOMAIN, {
            vacuum.DOMAIN: {
                CONF_PLATFORM: 'mqtt',
                CONF_NAME: 'mqtttest',
                ATTR_SUPPORTED_FEATURES: services_to_strings(ALL_SERVICES),
            }
        }))

        vacuum.turn_on(self.hass, 'vacuum.mqtttest')
        self.hass.block_till_done()
        self.assertEqual(('vacuum/command', 'turn_on', 0, False),
                         self.mock_publish.mock_calls[-2][1])

        vacuum.turn_off(self.hass, 'vacuum.mqtttest')
        self.hass.block_till_done()
        self.assertEqual(('vacuum/command', 'turn_off', 0, False),
                         self.mock_publish.mock_calls[-2][1])

        vacuum.stop(self.hass, 'vacuum.mqtttest')
        self.hass.block_till_done()
        self.assertEqual(('vacuum/command', 'stop', 0, False),
                         self.mock_publish.mock_calls[-2][1])

        vacuum.clean_spot(self.hass, 'vacuum.mqtttest')
        self.hass.block_till_done()
        self.assertEqual(('vacuum/command', 'clean_spot', 0, False),
                         self.mock_publish.mock_calls[-2][1])

        vacuum.locate(self.hass, 'vacuum.mqtttest')
        self.hass.block_till_done()
        self.assertEqual(('vacuum/command', 'locate', 0, False),
                         self.mock_publish.mock_calls[-2][1])

        vacuum.start_pause(self.hass, 'vacuum.mqtttest')
        self.hass.block_till_done()
        self.assertEqual(('vacuum/command', 'start_pause', 0, False),
                         self.mock_publish.mock_calls[-2][1])

        vacuum.return_to_base(self.hass, 'vacuum.mqtttest')
        self.hass.block_till_done()
        self.assertEqual(('vacuum/command', 'return_to_base', 0, False),
                         self.mock_publish.mock_calls[-2][1])

        vacuum.set_fan_speed(self.hass, 'high', 'vacuum.mqtttest')
        self.hass.block_till_done()
        self.assertEqual(
            ('vacuum/set_fan_speed', 'high', 0, False),
            self.mock_publish.mock_calls[-2][1]
        )

        vacuum.send_command(self.hass, '44 FE 93', entity_id='vacuum.mqtttest')
        self.hass.block_till_done()
        self.assertEqual(
            ('vacuum/send_command', '44 FE 93', 0, False),
            self.mock_publish.mock_calls[-2][1]
        )

    def test_status(self):
        """Test status updates from the vacuum."""
        self.assertTrue(setup_component(self.hass, vacuum.DOMAIN, {
            vacuum.DOMAIN: {
                CONF_PLATFORM: 'mqtt',
                CONF_NAME: 'mqtttest',
                ATTR_SUPPORTED_FEATURES: services_to_strings(ALL_SERVICES),
            }
        }))

        message = """{
            "battery_level": 54,
            "cleaning": true,
            "docked": false,
            "charging": false,
            "fan_speed": "max"
        }"""
        fire_mqtt_message(self.hass, 'vacuum/state', message)
        self.hass.block_till_done()
        state = self.hass.states.get('vacuum.mqtttest')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(
            'mdi:battery-50',
            state.attributes.get(ATTR_BATTERY_ICON)
        )
        self.assertEqual(54, state.attributes.get(ATTR_BATTERY_LEVEL))
        self.assertEqual('max', state.attributes.get(ATTR_FAN_SPEED))

        message = """{
            "battery_level": 61,
            "docked": true,
            "cleaning": false,
            "charging": true,
            "fan_speed": "min"
        }"""

        fire_mqtt_message(self.hass, 'vacuum/state', message)
        self.hass.block_till_done()
        state = self.hass.states.get('vacuum.mqtttest')
        self.assertEqual(STATE_OFF, state.state)
        self.assertEqual(
            'mdi:battery-charging-60',
            state.attributes.get(ATTR_BATTERY_ICON)
        )
        self.assertEqual(61, state.attributes.get(ATTR_BATTERY_LEVEL))
        self.assertEqual('min', state.attributes.get(ATTR_FAN_SPEED))

    def test_battery_template(self):
        """Tests that you can use non-default templates for battery_level."""
        self.assertTrue(setup_component(self.hass, vacuum.DOMAIN, {
            vacuum.DOMAIN: {
                CONF_PLATFORM: 'mqtt',
                CONF_NAME: 'mqtttest',
                ATTR_SUPPORTED_FEATURES: services_to_strings(ALL_SERVICES),
                CONF_BATTERY_LEVEL_TOPIC: "retroroomba/battery_level",
                CONF_BATTERY_LEVEL_TEMPLATE: "{{ value }}"
            }
        }))

        fire_mqtt_message(self.hass, 'retroroomba/battery_level', '54')
        self.hass.block_till_done()
        state = self.hass.states.get('vacuum.mqtttest')
        self.assertEqual(54, state.attributes.get(ATTR_BATTERY_LEVEL))
        self.assertEqual(state.attributes.get(ATTR_BATTERY_ICON),
                         'mdi:battery-50')

    def test_status_invalid_json(self):
        """Test to make sure nothing breaks if the vacuum sends bad JSON."""
        self.assertTrue(setup_component(self.hass, vacuum.DOMAIN, {
            vacuum.DOMAIN: {
                CONF_PLATFORM: 'mqtt',
                CONF_NAME: 'mqtttest',
            }
        }))

        fire_mqtt_message(self.hass, 'vacuum/state', '{"asdfasas false}')
        self.hass.block_till_done()
        state = self.hass.states.get('vacuum.mqtttest')
        self.assertEqual(STATE_OFF, state.state)
        self.assertEqual("Stopped", state.attributes.get(ATTR_STATUS))
