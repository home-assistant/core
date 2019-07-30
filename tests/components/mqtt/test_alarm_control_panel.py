"""The tests the MQTT alarm control panel component."""
import json
from unittest.mock import ANY

from homeassistant.components import alarm_control_panel, mqtt
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED, STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED,
    STATE_UNAVAILABLE, STATE_UNKNOWN)

from tests.common import (
    MockConfigEntry, assert_setup_component, async_fire_mqtt_message,
    async_mock_mqtt_component, async_setup_component, mock_registry)
from tests.components.alarm_control_panel import common

CODE = 'HELLO_CODE'


async def test_fail_setup_without_state_topic(hass, mqtt_mock):
    """Test for failing with no state topic."""
    with assert_setup_component(0) as config:
        assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'command_topic': 'alarm/command'
            }
        })
        assert not config[alarm_control_panel.DOMAIN]


async def test_fail_setup_without_command_topic(hass, mqtt_mock):
    """Test failing with no command topic."""
    with assert_setup_component(0):
        assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'state_topic': 'alarm/state'
            }
        })


async def test_update_state_via_state_topic(hass, mqtt_mock):
    """Test updating with via state topic."""
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
        }
    })

    entity_id = 'alarm_control_panel.test'

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    for state in (STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME,
                  STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_NIGHT,
                  STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED):
        async_fire_mqtt_message(hass, 'alarm/state', state)
        assert hass.states.get(entity_id).state == state


async def test_ignore_update_state_if_unknown_via_state_topic(hass, mqtt_mock):
    """Test ignoring updates via state topic."""
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
        }
    })

    entity_id = 'alarm_control_panel.test'

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, 'alarm/state', 'unsupported state')
    assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_arm_home_publishes_mqtt(hass, mqtt_mock):
    """Test publishing of MQTT messages while armed."""
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
        }
    })

    await common.async_alarm_arm_home(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        'alarm/command', 'ARM_HOME', 0, False)


async def test_arm_home_not_publishes_mqtt_with_invalid_code_when_req(
        hass, mqtt_mock):
    """Test not publishing of MQTT messages with invalid.

    When code_arm_required = True
    """
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
            'code': '1234',
            'code_arm_required': True
        }
    })

    call_count = mqtt_mock.async_publish.call_count
    await common.async_alarm_arm_home(hass, 'abcd')
    assert mqtt_mock.async_publish.call_count == call_count


async def test_arm_home_publishes_mqtt_when_code_not_req(hass, mqtt_mock):
    """Test publishing of MQTT messages.

    When code_arm_required = False
    """
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
            'code': '1234',
            'code_arm_required': False
        }
    })

    await common.async_alarm_arm_home(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        'alarm/command', 'ARM_HOME', 0, False)


async def test_arm_away_publishes_mqtt(hass, mqtt_mock):
    """Test publishing of MQTT messages while armed."""
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
        }
    })

    await common.async_alarm_arm_away(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        'alarm/command', 'ARM_AWAY', 0, False)


async def test_arm_away_not_publishes_mqtt_with_invalid_code_when_req(
        hass, mqtt_mock):
    """Test not publishing of MQTT messages with invalid code.

    When code_arm_required = True
    """
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
            'code': '1234',
            'code_arm_required': True
        }
    })

    call_count = mqtt_mock.async_publish.call_count
    await common.async_alarm_arm_away(hass, 'abcd')
    assert mqtt_mock.async_publish.call_count == call_count


async def test_arm_away_publishes_mqtt_when_code_not_req(hass, mqtt_mock):
    """Test publishing of MQTT messages.

    When code_arm_required = False
    """
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
            'code': '1234',
            'code_arm_required': False
        }
    })

    await common.async_alarm_arm_away(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        'alarm/command', 'ARM_AWAY', 0, False)


async def test_arm_night_publishes_mqtt(hass, mqtt_mock):
    """Test publishing of MQTT messages while armed."""
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
        }
    })

    await common.async_alarm_arm_night(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        'alarm/command', 'ARM_NIGHT', 0, False)


async def test_arm_night_not_publishes_mqtt_with_invalid_code_when_req(
        hass, mqtt_mock):
    """Test not publishing of MQTT messages with invalid code.

    When code_arm_required = True
    """
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
            'code': '1234',
            'code_arm_required': True
        }
    })

    call_count = mqtt_mock.async_publish.call_count
    await common.async_alarm_arm_night(hass, 'abcd')
    assert mqtt_mock.async_publish.call_count == call_count


async def test_arm_night_publishes_mqtt_when_code_not_req(hass, mqtt_mock):
    """Test publishing of MQTT messages.

    When code_arm_required = False
    """
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
            'code': '1234',
            'code_arm_required': False
        }
    })

    await common.async_alarm_arm_night(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        'alarm/command', 'ARM_NIGHT', 0, False)


async def test_disarm_publishes_mqtt(hass, mqtt_mock):
    """Test publishing of MQTT messages while disarmed."""
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
        }
    })

    await common.async_alarm_disarm(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        'alarm/command', 'DISARM', 0, False)


async def test_disarm_publishes_mqtt_with_template(hass, mqtt_mock):
    """Test publishing of MQTT messages while disarmed.

    When command_template set to output json
    """
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
            'code': '1234',
            'command_template': '{\"action\":\"{{ action }}\",'
                                '\"code\":\"{{ code }}\"}',
        }
    })

    await common.async_alarm_disarm(hass, 1234)
    mqtt_mock.async_publish.assert_called_once_with(
        'alarm/command', '{\"action\":\"DISARM\",\"code\":\"1234\"}',
        0,
        False)


async def test_disarm_publishes_mqtt_when_code_not_req(hass, mqtt_mock):
    """Test publishing of MQTT messages while disarmed.

    When code_disarm_required = False
    """
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
            'code': '1234',
            'code_disarm_required': False
        }
    })

    await common.async_alarm_disarm(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        'alarm/command', 'DISARM', 0, False)


async def test_disarm_not_publishes_mqtt_with_invalid_code_when_req(
        hass, mqtt_mock):
    """Test not publishing of MQTT messages with invalid code.

    When code_disarm_required = True
    """
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
            'code': '1234',
            'code_disarm_required': True
        }
    })

    call_count = mqtt_mock.async_publish.call_count
    await common.async_alarm_disarm(hass, 'abcd')
    assert mqtt_mock.async_publish.call_count == call_count


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'alarm/state',
            'command_topic': 'alarm/command',
            'code': '1234',
            'availability_topic': 'availability-topic'
        }
    })

    state = hass.states.get('alarm_control_panel.test')
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'online')

    state = hass.states.get('alarm_control_panel.test')
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'offline')

    state = hass.states.get('alarm_control_panel.test')
    assert state.state == STATE_UNAVAILABLE


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
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

    state = hass.states.get('alarm_control_panel.test')
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'good')

    state = hass.states.get('alarm_control_panel.test')
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'nogood')

    state = hass.states.get('alarm_control_panel.test')
    assert state.state == STATE_UNAVAILABLE


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test-topic',
            'state_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '{ "val": "100" }')
    state = hass.states.get('alarm_control_panel.test')

    assert state.attributes.get('val') == '100'


async def test_update_state_via_state_topic_template(hass, mqtt_mock):
    """Test updating with template_value via state topic."""
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test-topic',
            'state_topic': 'test-topic',
            'value_template': '\
                {% if (value | int)  == 100 %}\
                  armed_away\
                {% else %}\
                   disarmed\
                {% endif %}'
            }
    })

    state = hass.states.get('alarm_control_panel.test')
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, 'test-topic', '100')

    state = hass.states.get('alarm_control_panel.test')
    assert state.state == STATE_ALARM_ARMED_AWAY


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test-topic',
            'state_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '[ "list", "of", "things"]')
    state = hass.states.get('alarm_control_panel.test')

    assert state.attributes.get('val') is None
    assert 'JSON result was not a dictionary' in caplog.text


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        alarm_control_panel.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test-topic',
            'state_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', 'This is not JSON')

    state = hass.states.get('alarm_control_panel.test')
    assert state.attributes.get('val') is None
    assert 'Erroneous JSON: This is not JSON' in caplog.text


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)
    data1 = (
        '{ "name": "Beer",'
        '  "command_topic": "test_topic",'
        '  "json_attributes_topic": "attr-topic1" }'
    )
    data2 = (
        '{ "name": "Beer",'
        '  "command_topic": "test_topic",'
        '  "json_attributes_topic": "attr-topic2" }'
    )
    async_fire_mqtt_message(
        hass, 'homeassistant/alarm_control_panel/bla/config', data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "100" }')
    state = hass.states.get('alarm_control_panel.beer')
    assert state.attributes.get('val') == '100'

    # Change json_attributes_topic
    async_fire_mqtt_message(
        hass, 'homeassistant/alarm_control_panel/bla/config', data2)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "50" }')
    state = hass.states.get('alarm_control_panel.beer')
    assert state.attributes.get('val') == '100'

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, 'attr-topic2', '{ "val": "75" }')
    state = hass.states.get('alarm_control_panel.beer')
    assert state.attributes.get('val') == '75'


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
    assert len(hass.states.async_entity_ids(alarm_control_panel.DOMAIN)) == 1


async def test_discovery_removal_alarm(hass, mqtt_mock, caplog):
    """Test removal of discovered alarm_control_panel."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
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

    state = hass.states.get('alarm_control_panel.beer')
    assert state is None


async def test_discovery_update_alarm(hass, mqtt_mock, caplog):
    """Test update of discovered alarm_control_panel."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic",'
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

    state = hass.states.get('alarm_control_panel.beer')
    assert state is not None
    assert state.name == 'Milk'

    state = hass.states.get('alarm_control_panel.milk')
    assert state is None


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass,
                            'homeassistant/alarm_control_panel/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('alarm_control_panel.beer')
    assert state is None

    async_fire_mqtt_message(hass,
                            'homeassistant/alarm_control_panel/bla/config',
                            data2)
    await hass.async_block_till_done()

    state = hass.states.get('alarm_control_panel.milk')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('alarm_control_panel.beer')
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

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.identifiers == {('mqtt', 'helloworld')}
    assert device.connections == {('mac', "02:5b:26:a8:dc:12")}
    assert device.manufacturer == 'Whatever'
    assert device.name == 'Beer'
    assert device.model == 'Glass'
    assert device.sw_version == '0.1-beta'


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, 'homeassistant', {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    config = {
        'platform': 'mqtt',
        'name': 'Test 1',
        'state_topic': 'test-topic',
        'command_topic': 'test-command-topic',
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
    }

    data = json.dumps(config)
    async_fire_mqtt_message(
        hass, 'homeassistant/alarm_control_panel/bla/config', data)
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.name == 'Beer'

    config['device']['name'] = 'Milk'
    data = json.dumps(config)
    async_fire_mqtt_message(
        hass, 'homeassistant/alarm_control_panel/bla/config', data)
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.name == 'Milk'


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

    state = hass.states.get('alarm_control_panel.beer')
    assert state is None

    state = hass.states.get('alarm_control_panel.milk')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
