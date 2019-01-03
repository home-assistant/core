"""The tests the MQTT alarm control panel component."""
import json
import unittest
from unittest.mock import ANY

from homeassistant.setup import setup_component
from homeassistant.const import (
    STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED, STATE_UNAVAILABLE,
    STATE_UNKNOWN)
from homeassistant.components import alarm_control_panel, mqtt
from homeassistant.components.mqtt.discovery import async_start

from tests.common import (
    assert_setup_component, async_fire_mqtt_message, async_mock_mqtt_component,
    async_setup_component, fire_mqtt_message, get_test_home_assistant,
    mock_mqtt_component, MockConfigEntry, mock_registry)
from tests.components.alarm_control_panel import common

CODE = 'HELLO_CODE'


class TestAlarmControlPanelMQTT(unittest.TestCase):
    """Test the manual alarm module."""

    # pylint: disable=invalid-name

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down stuff we started."""
        self.hass.stop()

    def test_fail_setup_without_state_topic(self):
        """Test for failing with no state topic."""
        with assert_setup_component(0) as config:
            assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
                alarm_control_panel.DOMAIN: {
                    'platform': 'mqtt',
                    'command_topic': 'alarm/command'
                }
            })
            assert not config[alarm_control_panel.DOMAIN]

    def test_fail_setup_without_command_topic(self):
        """Test failing with no command topic."""
        with assert_setup_component(0):
            assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
                alarm_control_panel.DOMAIN: {
                    'platform': 'mqtt',
                    'state_topic': 'alarm/state'
                }
            })

    def test_update_state_via_state_topic(self):
        """Test updating with via state topic."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
            }
        })

        entity_id = 'alarm_control_panel.test'

        assert STATE_UNKNOWN == \
            self.hass.states.get(entity_id).state

        for state in (STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME,
                      STATE_ALARM_ARMED_AWAY, STATE_ALARM_PENDING,
                      STATE_ALARM_TRIGGERED):
            fire_mqtt_message(self.hass, 'alarm/state', state)
            self.hass.block_till_done()
            assert state == self.hass.states.get(entity_id).state

    def test_ignore_update_state_if_unknown_via_state_topic(self):
        """Test ignoring updates via state topic."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
            }
        })

        entity_id = 'alarm_control_panel.test'

        assert STATE_UNKNOWN == \
            self.hass.states.get(entity_id).state

        fire_mqtt_message(self.hass, 'alarm/state', 'unsupported state')
        self.hass.block_till_done()
        assert STATE_UNKNOWN == self.hass.states.get(entity_id).state

    def test_arm_home_publishes_mqtt(self):
        """Test publishing of MQTT messages while armed."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
            }
        })

        common.alarm_arm_home(self.hass)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            'alarm/command', 'ARM_HOME', 0, False)

    def test_arm_home_not_publishes_mqtt_with_invalid_code(self):
        """Test not publishing of MQTT messages with invalid code."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
                'code': '1234'
            }
        })

        call_count = self.mock_publish.call_count
        common.alarm_arm_home(self.hass, 'abcd')
        self.hass.block_till_done()
        assert call_count == self.mock_publish.call_count

    def test_arm_away_publishes_mqtt(self):
        """Test publishing of MQTT messages while armed."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
            }
        })

        common.alarm_arm_away(self.hass)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            'alarm/command', 'ARM_AWAY', 0, False)

    def test_arm_away_not_publishes_mqtt_with_invalid_code(self):
        """Test not publishing of MQTT messages with invalid code."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
                'code': '1234'
            }
        })

        call_count = self.mock_publish.call_count
        common.alarm_arm_away(self.hass, 'abcd')
        self.hass.block_till_done()
        assert call_count == self.mock_publish.call_count

    def test_disarm_publishes_mqtt(self):
        """Test publishing of MQTT messages while disarmed."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
            }
        })

        common.alarm_disarm(self.hass)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            'alarm/command', 'DISARM', 0, False)

    def test_disarm_not_publishes_mqtt_with_invalid_code(self):
        """Test not publishing of MQTT messages with invalid code."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
                'code': '1234'
            }
        })

        call_count = self.mock_publish.call_count
        common.alarm_disarm(self.hass, 'abcd')
        self.hass.block_till_done()
        assert call_count == self.mock_publish.call_count

    def test_default_availability_payload(self):
        """Test availability by default payload with defined topic."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
                'code': '1234',
                'availability_topic': 'availability-topic'
            }
        })

        state = self.hass.states.get('alarm_control_panel.test')
        assert STATE_UNAVAILABLE == state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'online')
        self.hass.block_till_done()

        state = self.hass.states.get('alarm_control_panel.test')
        assert STATE_UNAVAILABLE != state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'offline')
        self.hass.block_till_done()

        state = self.hass.states.get('alarm_control_panel.test')
        assert STATE_UNAVAILABLE == state.state

    def test_custom_availability_payload(self):
        """Test availability by custom payload with defined topic."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
                'code': '1234',
                'availability_topic': 'availability-topic',
                'payload_available': 'good',
                'payload_not_available': 'nogood'
            }
        })

        state = self.hass.states.get('alarm_control_panel.test')
        assert STATE_UNAVAILABLE == state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'good')


async def test_unique_id(hass):
    """Test unique id option only creates one alarm per unique_id."""
    await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: [{
            'platform': 'mqtt',
            'name': 'Test 1',
            'state_topic': 'test-topic',
            'command_topic': 'test_topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }, {
            'platform': 'mqtt',
            'name': 'Test 2',
            'state_topic': 'test-topic',
            'command_topic': 'test_topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })
    async_fire_mqtt_message(hass, 'test-topic', 'payload')
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(alarm_control_panel.DOMAIN)) == 1


async def test_discovery_removal_alarm(hass, mqtt_mock, caplog):
    """Test removal of discovered alarm_control_panel."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data = (
        '{ "name": "Beer",'
        '  "status_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass,
                            'homeassistant/alarm_control_panel/bla/config',
                            data)
    await hass.async_block_till_done()

    state = hass.states.get('alarm_control_panel.beer')
    assert state is not None
    assert state.name == 'Beer'

    async_fire_mqtt_message(hass,
                            'homeassistant/alarm_control_panel/bla/config',
                            '')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('alarm_control_panel.beer')
    assert state is None


async def test_discovery_update_alarm(hass, mqtt_mock, caplog):
    """Test removal of discovered alarm_control_panel."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer",'
        '  "status_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "status_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass,
                            'homeassistant/alarm_control_panel/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('alarm_control_panel.beer')
    assert state is not None
    assert state.name == 'Beer'

    async_fire_mqtt_message(hass,
                            'homeassistant/alarm_control_panel/bla/config',
                            data2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('alarm_control_panel.beer')
    assert state is not None
    assert state.name == 'Milk'

    state = hass.states.get('alarm_control_panel.milk')
    assert state is None


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT alarm control panel device registry integration."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, 'homeassistant', {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps({
        'platform': 'mqtt',
        'name': 'Test 1',
        'state_topic': 'test-topic',
        'command_topic': 'test-topic',
        'device': {
            'identifiers': ['helloworld'],
            'connections': [
                ["mac", "02:5b:26:a8:dc:12"],
            ],
            'manufacturer': 'Whatever',
            'name': 'Beer',
            'model': 'Glass',
            'sw_version': '0.1-beta',
        },
        'unique_id': 'veryunique'
    })
    async_fire_mqtt_message(
        hass, 'homeassistant/alarm_control_panel/bla/config', data)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.identifiers == {('mqtt', 'helloworld')}
    assert device.connections == {('mac', "02:5b:26:a8:dc:12")}
    assert device.manufacturer == 'Whatever'
    assert device.name == 'Beer'
    assert device.model == 'Glass'
    assert device.sw_version == '0.1-beta'


async def test_entity_id_update(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    registry = mock_registry(hass, {})
    mock_mqtt = await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: [{
            'platform': 'mqtt',
            'name': 'beer',
            'state_topic': 'test-topic',
            'command_topic': 'command-topic',
            'availability_topic': 'avty-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })

    state = hass.states.get('alarm_control_panel.beer')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.reset_mock()

    registry.async_update_entity(
        'alarm_control_panel.beer', new_entity_id='alarm_control_panel.milk')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('alarm_control_panel.beer')
    assert state is None

    state = hass.states.get('alarm_control_panel.milk')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
