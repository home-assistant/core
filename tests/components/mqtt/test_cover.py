"""The tests for the MQTT cover platform."""

import copy
from unittest.mock import patch

import pytest

from homeassistant.components import cover
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
)
from homeassistant.components.mqtt.const import CONF_STATE_TOPIC
from homeassistant.components.mqtt.cover import (
    CONF_GET_POSITION_TEMPLATE,
    CONF_GET_POSITION_TOPIC,
    CONF_SET_POSITION_TEMPLATE,
    CONF_SET_POSITION_TOPIC,
    CONF_TILT_COMMAND_TEMPLATE,
    CONF_TILT_COMMAND_TOPIC,
    CONF_TILT_STATUS_TEMPLATE,
    CONF_TILT_STATUS_TOPIC,
    MQTT_COVER_ATTRIBUTES_BLOCKED,
    MqttCover,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    CONF_VALUE_TEMPLATE,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_TOGGLE,
    SERVICE_TOGGLE_COVER_TILT,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.setup import async_setup_component

from .test_common import (
    help_test_availability_when_connection_lost,
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
    help_test_discovery_update_unchanged,
    help_test_encoding_subscribable_topics,
    help_test_entity_debug_info_message,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
    help_test_publishing_with_custom_encoding,
    help_test_reloadable,
    help_test_reloadable_late,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
    help_test_setup_manual_entity_from_yaml,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message

DEFAULT_CONFIG = {
    cover.DOMAIN: {"platform": "mqtt", "name": "test", "state_topic": "test-topic"}
}


@pytest.fixture(autouse=True)
def cover_platform_only():
    """Only setup the cover platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.COVER]):
        yield


async def test_state_via_state_topic(hass, mqtt_mock_entry_with_yaml_config):
    """Test the controlling state via topic."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", STATE_CLOSED)

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED

    async_fire_mqtt_message(hass, "state-topic", STATE_OPEN)

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN


async def test_opening_and_closing_state_via_custom_state_payload(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test the controlling opening and closing state via a custom payload."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "state_opening": "34",
                "state_closing": "--43",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "34")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPENING

    async_fire_mqtt_message(hass, "state-topic", "--43")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSING

    async_fire_mqtt_message(hass, "state-topic", STATE_CLOSED)

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED


async def test_open_closed_state_from_position_optimistic(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test the state after setting the position using optimistic mode."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "position_topic": "position-topic",
                "set_position_topic": "set-position-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "optimistic": True,
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: 0},
        blocking=True,
    )

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: 100},
        blocking=True,
    )

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN
    assert state.attributes.get(ATTR_ASSUMED_STATE)


async def test_position_via_position_topic(hass, mqtt_mock_entry_with_yaml_config):
    """Test the controlling state via topic."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "position_topic": "get-position-topic",
                "position_open": 100,
                "position_closed": 0,
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "get-position-topic", "0")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED

    async_fire_mqtt_message(hass, "get-position-topic", "100")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN


async def test_state_via_template(hass, mqtt_mock_entry_with_yaml_config):
    """Test the controlling state via topic."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "value_template": "\
                {% if (value | multiply(0.01) | int) == 0  %}\
                  closed\
                {% else %}\
                  open\
                {% endif %}",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "state-topic", "10000")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "state-topic", "99")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED


async def test_state_via_template_and_entity_id(hass, mqtt_mock_entry_with_yaml_config):
    """Test the controlling state via topic."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "value_template": '\
                {% if value == "open" or value == "closed"  %}\
                  {{ value }}\
                {% else %}\
                  {{ states(entity_id) }}\
                {% endif %}',
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "state-topic", "open")
    async_fire_mqtt_message(hass, "state-topic", "invalid")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "state-topic", "closed")
    async_fire_mqtt_message(hass, "state-topic", "invalid")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED


async def test_state_via_template_with_json_value(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test the controlling state via topic with JSON value."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "value_template": "{{ value_json.Var1 }}",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "state-topic", '{ "Var1": "open", "Var2": "other" }')

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(
        hass, "state-topic", '{ "Var1": "closed", "Var2": "other" }'
    )

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED

    async_fire_mqtt_message(hass, "state-topic", '{ "Var2": "other" }')
    assert (
        "Template variable warning: 'dict object' has no attribute 'Var1' when rendering"
    ) in caplog.text


async def test_position_via_template_and_entity_id(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test the controlling state via topic."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "position_topic": "get-position-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "position_template": '\
                {% if state_attr(entity_id, "current_position") == None %}\
                  {{ value }}\
                {% else %}\
                  {{ state_attr(entity_id, "current_position") + value | int }}\
                {% endif %}',
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "get-position-topic", "10")

    current_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position == 10

    async_fire_mqtt_message(hass, "get-position-topic", "10")

    current_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position == 20


@pytest.mark.parametrize(
    "config, assumed_state",
    [
        ({"command_topic": "abc"}, True),
        ({"command_topic": "abc", "state_topic": "abc"}, False),
        # ({"set_position_topic": "abc"}, True), - not a valid configuration
        ({"set_position_topic": "abc", "position_topic": "abc"}, False),
        ({"tilt_command_topic": "abc"}, True),
        ({"tilt_command_topic": "abc", "tilt_status_topic": "abc"}, False),
    ],
)
async def test_optimistic_flag(
    hass, mqtt_mock_entry_with_yaml_config, config, assumed_state
):
    """Test assumed_state is set correctly."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {cover.DOMAIN: {**config, "platform": "mqtt", "name": "test", "qos": 0}},
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN
    if assumed_state:
        assert ATTR_ASSUMED_STATE in state.attributes
    else:
        assert ATTR_ASSUMED_STATE not in state.attributes


async def test_optimistic_state_change(hass, mqtt_mock_entry_with_yaml_config):
    """Test changing state optimistically."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "qos": 0,
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OPEN", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "CLOSE", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OPEN", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "CLOSE", 0, False)
    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED


async def test_optimistic_state_change_with_position(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test changing state optimistically."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "optimistic": True,
                "command_topic": "command-topic",
                "position_topic": "position-topic",
                "qos": 0,
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(ATTR_CURRENT_POSITION) is None

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OPEN", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 100

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "CLOSE", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 0

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OPEN", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 100

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "CLOSE", 0, False)
    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 0


async def test_send_open_cover_command(hass, mqtt_mock_entry_with_yaml_config):
    """Test the sending of open_cover."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 2,
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OPEN", 2, False)
    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN


async def test_send_close_cover_command(hass, mqtt_mock_entry_with_yaml_config):
    """Test the sending of close_cover."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 2,
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "CLOSE", 2, False)
    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN


async def test_send_stop__cover_command(hass, mqtt_mock_entry_with_yaml_config):
    """Test the sending of stop_cover."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 2,
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "STOP", 2, False)
    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN


async def test_current_cover_position(hass, mqtt_mock_entry_with_yaml_config):
    """Test the current cover position."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "position_topic": "get-position-topic",
                "command_topic": "command-topic",
                "position_open": 100,
                "position_closed": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state_attributes_dict = hass.states.get("cover.test").attributes
    assert ATTR_CURRENT_POSITION not in state_attributes_dict
    assert ATTR_CURRENT_TILT_POSITION not in state_attributes_dict
    assert 4 & hass.states.get("cover.test").attributes["supported_features"] != 4

    async_fire_mqtt_message(hass, "get-position-topic", "0")
    current_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position == 0

    async_fire_mqtt_message(hass, "get-position-topic", "50")
    current_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position == 50

    async_fire_mqtt_message(hass, "get-position-topic", "non-numeric")
    current_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position == 50

    async_fire_mqtt_message(hass, "get-position-topic", "101")
    current_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position == 100


async def test_current_cover_position_inverted(hass, mqtt_mock_entry_with_yaml_config):
    """Test the current cover position."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "position_topic": "get-position-topic",
                "command_topic": "command-topic",
                "position_open": 0,
                "position_closed": 100,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state_attributes_dict = hass.states.get("cover.test").attributes
    assert ATTR_CURRENT_POSITION not in state_attributes_dict
    assert ATTR_CURRENT_TILT_POSITION not in state_attributes_dict
    assert 4 & hass.states.get("cover.test").attributes["supported_features"] != 4

    async_fire_mqtt_message(hass, "get-position-topic", "100")
    current_percentage_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_percentage_cover_position == 0
    assert hass.states.get("cover.test").state == STATE_CLOSED

    async_fire_mqtt_message(hass, "get-position-topic", "0")
    current_percentage_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_percentage_cover_position == 100
    assert hass.states.get("cover.test").state == STATE_OPEN

    async_fire_mqtt_message(hass, "get-position-topic", "50")
    current_percentage_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_percentage_cover_position == 50
    assert hass.states.get("cover.test").state == STATE_OPEN

    async_fire_mqtt_message(hass, "get-position-topic", "non-numeric")
    current_percentage_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_percentage_cover_position == 50
    assert hass.states.get("cover.test").state == STATE_OPEN

    async_fire_mqtt_message(hass, "get-position-topic", "101")
    current_percentage_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_percentage_cover_position == 0
    assert hass.states.get("cover.test").state == STATE_CLOSED


async def test_optimistic_position(hass, mqtt_mock_entry_no_yaml_config):
    """Test optimistic position is not supported."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "set_position_topic": "set-position-topic",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    state = hass.states.get("cover.test")
    assert state is None


async def test_position_update(hass, mqtt_mock_entry_with_yaml_config):
    """Test cover position update from received MQTT message."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "position_topic": "get-position-topic",
                "command_topic": "command-topic",
                "set_position_topic": "set-position-topic",
                "position_open": 100,
                "position_closed": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state_attributes_dict = hass.states.get("cover.test").attributes
    assert ATTR_CURRENT_POSITION not in state_attributes_dict
    assert ATTR_CURRENT_TILT_POSITION not in state_attributes_dict
    assert 4 & hass.states.get("cover.test").attributes["supported_features"] == 4

    async_fire_mqtt_message(hass, "get-position-topic", "22")
    state_attributes_dict = hass.states.get("cover.test").attributes
    assert ATTR_CURRENT_POSITION in state_attributes_dict
    assert ATTR_CURRENT_TILT_POSITION not in state_attributes_dict
    current_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position == 22


@pytest.mark.parametrize(
    "pos_template,pos_call,pos_message",
    [("{{position-1}}", 43, "42"), ("{{100-62}}", 100, "38")],
)
async def test_set_position_templated(
    hass, mqtt_mock_entry_with_yaml_config, pos_template, pos_call, pos_message
):
    """Test setting cover position via template."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "position_topic": "get-position-topic",
                "command_topic": "command-topic",
                "position_open": 100,
                "position_closed": 0,
                "set_position_topic": "set-position-topic",
                "set_position_template": pos_template,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: pos_call},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "set-position-topic", pos_message, 0, False
    )


async def test_set_position_templated_and_attributes(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test setting cover position via template and using entities attributes."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "position_topic": "get-position-topic",
                "command_topic": "command-topic",
                "position_open": 100,
                "position_closed": 0,
                "set_position_topic": "set-position-topic",
                "set_position_template": '\
                {% if position > 99 %}\
                  {% if state_attr(entity_id, "current_position") == None %}\
                    {{ 5 }}\
                  {% else %}\
                    {{ 23 }}\
                  {% endif %}\
                {% else %}\
                  {{ 42 }}\
                {% endif %}',
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: 100},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("set-position-topic", "5", 0, False)


async def test_set_tilt_templated(hass, mqtt_mock_entry_with_yaml_config):
    """Test setting cover tilt position via template."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "position_topic": "get-position-topic",
                "command_topic": "command-topic",
                "tilt_command_topic": "tilt-command-topic",
                "position_open": 100,
                "position_closed": 0,
                "set_position_topic": "set-position-topic",
                "set_position_template": "{{position-1}}",
                "tilt_command_template": "{{tilt_position+1}}",
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: 41},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "42", 0, False
    )


async def test_set_tilt_templated_and_attributes(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test setting cover tilt position via template and using entities attributes."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "position_topic": "get-position-topic",
                "command_topic": "command-topic",
                "tilt_command_topic": "tilt-command-topic",
                "position_open": 100,
                "position_closed": 0,
                "set_position_topic": "set-position-topic",
                "set_position_template": "{{position-1}}",
                "tilt_command_template": "{"
                '"entity_id": "{{ entity_id }}",'
                '"value": {{ value }},'
                '"tilt_position": {{ tilt_position }}'
                "}",
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: 45},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic",
        '{"entity_id": "cover.test","value": 45,"tilt_position": 45}',
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic",
        '{"entity_id": "cover.test","value": 100,"tilt_position": 100}',
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic",
        '{"entity_id": "cover.test","value": 0,"tilt_position": 0}',
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_TOGGLE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic",
        '{"entity_id": "cover.test","value": 100,"tilt_position": 100}',
        0,
        False,
    )


async def test_set_position_untemplated(hass, mqtt_mock_entry_with_yaml_config):
    """Test setting cover position via template."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "position_topic": "state-topic",
                "command_topic": "command-topic",
                "set_position_topic": "position-topic",
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: 62},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("position-topic", "62", 0, False)


async def test_set_position_untemplated_custom_percentage_range(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test setting cover position via template."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "position_topic": "state-topic",
                "command_topic": "command-topic",
                "set_position_topic": "position-topic",
                "position_open": 0,
                "position_closed": 100,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: 38},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("position-topic", "62", 0, False)


async def test_no_command_topic(hass, mqtt_mock_entry_with_yaml_config):
    """Test with no command topic."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command",
                "tilt_status_topic": "tilt-status",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    assert hass.states.get("cover.test").attributes["supported_features"] == 240


async def test_no_payload_close(hass, mqtt_mock_entry_with_yaml_config):
    """Test with no close payload."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": None,
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    assert hass.states.get("cover.test").attributes["supported_features"] == 9


async def test_no_payload_open(hass, mqtt_mock_entry_with_yaml_config):
    """Test with no open payload."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": None,
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    assert hass.states.get("cover.test").attributes["supported_features"] == 10


async def test_no_payload_stop(hass, mqtt_mock_entry_with_yaml_config):
    """Test with no stop payload."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": None,
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    assert hass.states.get("cover.test").attributes["supported_features"] == 3


async def test_with_command_topic_and_tilt(hass, mqtt_mock_entry_with_yaml_config):
    """Test with command topic and tilt config."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "command_topic": "test",
                "platform": "mqtt",
                "name": "test",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command",
                "tilt_status_topic": "tilt-status",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    assert hass.states.get("cover.test").attributes["supported_features"] == 251


async def test_tilt_defaults(hass, mqtt_mock_entry_with_yaml_config):
    """Test the defaults."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command",
                "tilt_status_topic": "tilt-status",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state_attributes_dict = hass.states.get("cover.test").attributes
    # Tilt position is not yet known
    assert ATTR_CURRENT_TILT_POSITION not in state_attributes_dict


async def test_tilt_via_invocation_defaults(hass, mqtt_mock_entry_with_yaml_config):
    """Test tilt defaults on close/open."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "100", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", "0", 0, False)
    mqtt_mock.async_publish.reset_mock()

    # Close tilt status would be received from device when non-optimistic
    async_fire_mqtt_message(hass, "tilt-status-topic", "0")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 0

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_TOGGLE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "100", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Open tilt status would be received from device when non-optimistic
    async_fire_mqtt_message(hass, "tilt-status-topic", "100")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 100

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_TOGGLE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", "0", 0, False)


async def test_tilt_given_value(hass, mqtt_mock_entry_with_yaml_config):
    """Test tilting to a given value."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
                "tilt_opened_value": 80,
                "tilt_closed_value": 25,
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "80", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "25", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Close tilt status would be received from device when non-optimistic
    async_fire_mqtt_message(hass, "tilt-status-topic", "25")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 25

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_TOGGLE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "80", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Open tilt status would be received from device when non-optimistic
    async_fire_mqtt_message(hass, "tilt-status-topic", "80")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 80

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_TOGGLE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "25", 0, False
    )


async def test_tilt_given_value_optimistic(hass, mqtt_mock_entry_with_yaml_config):
    """Test tilting to a given value."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
                "tilt_opened_value": 80,
                "tilt_closed_value": 25,
                "tilt_optimistic": True,
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 80

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "80", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: 50},
        blocking=True,
    )

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 50

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "50", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 25

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "25", 0, False
    )


async def test_tilt_given_value_altered_range(hass, mqtt_mock_entry_with_yaml_config):
    """Test tilting to a given value."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
                "tilt_opened_value": 25,
                "tilt_closed_value": 0,
                "tilt_min": 0,
                "tilt_max": 50,
                "tilt_optimistic": True,
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 50

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "25", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 0

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", "0", 0, False)
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_TOGGLE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 50

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "25", 0, False
    )


async def test_tilt_via_topic(hass, mqtt_mock_entry_with_yaml_config):
    """Test tilt by updating status via MQTT."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "tilt-status-topic", "0")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 0

    async_fire_mqtt_message(hass, "tilt-status-topic", "50")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 50


async def test_tilt_via_topic_template(hass, mqtt_mock_entry_with_yaml_config):
    """Test tilt by updating status via MQTT and template."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
                "tilt_status_template": "{{ (value | multiply(0.01)) | int }}",
                "tilt_opened_value": 400,
                "tilt_closed_value": 125,
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "tilt-status-topic", "99")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 0

    async_fire_mqtt_message(hass, "tilt-status-topic", "5000")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 50


async def test_tilt_via_topic_template_json_value(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test tilt by updating status via MQTT and template with JSON value."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
                "tilt_status_template": "{{ value_json.Var1 }}",
                "tilt_opened_value": 400,
                "tilt_closed_value": 125,
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "tilt-status-topic", '{"Var1": 9, "Var2": 30}')

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 9

    async_fire_mqtt_message(hass, "tilt-status-topic", '{"Var1": 50, "Var2": 10}')

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 50

    async_fire_mqtt_message(hass, "tilt-status-topic", '{"Var2": 10}')

    assert (
        "Template variable warning: 'dict object' has no attribute 'Var1' when rendering"
    ) in caplog.text


async def test_tilt_via_topic_altered_range(hass, mqtt_mock_entry_with_yaml_config):
    """Test tilt status via MQTT with altered tilt range."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
                "tilt_min": 0,
                "tilt_max": 50,
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "tilt-status-topic", "0")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 0

    async_fire_mqtt_message(hass, "tilt-status-topic", "50")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 100

    async_fire_mqtt_message(hass, "tilt-status-topic", "25")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 50


async def test_tilt_status_out_of_range_warning(
    hass, caplog, mqtt_mock_entry_with_yaml_config
):
    """Test tilt status via MQTT tilt out of range warning message."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
                "tilt_min": 0,
                "tilt_max": 50,
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "tilt-status-topic", "60")

    assert (
        "Payload '60' is out of range, must be between '0' and '50' inclusive"
    ) in caplog.text


async def test_tilt_status_not_numeric_warning(
    hass, caplog, mqtt_mock_entry_with_yaml_config
):
    """Test tilt status via MQTT tilt not numeric warning message."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
                "tilt_min": 0,
                "tilt_max": 50,
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "tilt-status-topic", "abc")

    assert ("Payload 'abc' is not numeric") in caplog.text


async def test_tilt_via_topic_altered_range_inverted(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test tilt status via MQTT with altered tilt range and inverted tilt position."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
                "tilt_min": 50,
                "tilt_max": 0,
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "tilt-status-topic", "0")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 100

    async_fire_mqtt_message(hass, "tilt-status-topic", "50")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 0

    async_fire_mqtt_message(hass, "tilt-status-topic", "25")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 50


async def test_tilt_via_topic_template_altered_range(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test tilt status via MQTT and template with altered tilt range."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
                "tilt_status_template": "{{ (value | multiply(0.01)) | int }}",
                "tilt_opened_value": 400,
                "tilt_closed_value": 125,
                "tilt_min": 0,
                "tilt_max": 50,
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "tilt-status-topic", "99")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 0

    async_fire_mqtt_message(hass, "tilt-status-topic", "5000")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 100

    async_fire_mqtt_message(hass, "tilt-status-topic", "2500")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_tilt_position == 50


async def test_tilt_position(hass, mqtt_mock_entry_with_yaml_config):
    """Test tilt via method invocation."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: 50},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "50", 0, False
    )


async def test_tilt_position_templated(hass, mqtt_mock_entry_with_yaml_config):
    """Test tilt position via template."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
                "tilt_command_template": "{{100-32}}",
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: 100},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "68", 0, False
    )


async def test_tilt_position_altered_range(hass, mqtt_mock_entry_with_yaml_config):
    """Test tilt via method invocation with altered range."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "qos": 0,
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
                "tilt_command_topic": "tilt-command-topic",
                "tilt_status_topic": "tilt-status-topic",
                "tilt_opened_value": 400,
                "tilt_closed_value": 125,
                "tilt_min": 0,
                "tilt_max": 50,
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: 50},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "25", 0, False
    )


async def test_find_percentage_in_range_defaults(hass):
    """Test find percentage in range with default range."""
    mqtt_cover = MqttCover(
        hass,
        {
            "name": "cover.test",
            "state_topic": "state-topic",
            "get_position_topic": None,
            "command_topic": "command-topic",
            "availability_topic": None,
            "tilt_command_topic": "tilt-command-topic",
            "tilt_status_topic": "tilt-status-topic",
            "qos": 0,
            "retain": False,
            "state_open": "OPEN",
            "state_closed": "CLOSE",
            "position_open": 100,
            "position_closed": 0,
            "payload_open": "OPEN",
            "payload_close": "CLOSE",
            "payload_stop": "STOP",
            "payload_available": None,
            "payload_not_available": None,
            "optimistic": False,
            "value_template": None,
            "tilt_open_position": 100,
            "tilt_closed_position": 0,
            "tilt_min": 0,
            "tilt_max": 100,
            "tilt_optimistic": False,
            "set_position_topic": None,
            "set_position_template": None,
            "unique_id": None,
            "device_config": None,
        },
        None,
        None,
    )

    assert mqtt_cover.find_percentage_in_range(44) == 44
    assert mqtt_cover.find_percentage_in_range(44, "cover") == 44


async def test_find_percentage_in_range_altered(hass):
    """Test find percentage in range with altered range."""
    mqtt_cover = MqttCover(
        hass,
        {
            "name": "cover.test",
            "state_topic": "state-topic",
            "get_position_topic": None,
            "command_topic": "command-topic",
            "availability_topic": None,
            "tilt_command_topic": "tilt-command-topic",
            "tilt_status_topic": "tilt-status-topic",
            "qos": 0,
            "retain": False,
            "state_open": "OPEN",
            "state_closed": "CLOSE",
            "position_open": 180,
            "position_closed": 80,
            "payload_open": "OPEN",
            "payload_close": "CLOSE",
            "payload_stop": "STOP",
            "payload_available": None,
            "payload_not_available": None,
            "optimistic": False,
            "value_template": None,
            "tilt_open_position": 180,
            "tilt_closed_position": 80,
            "tilt_min": 80,
            "tilt_max": 180,
            "tilt_optimistic": False,
            "set_position_topic": None,
            "set_position_template": None,
            "unique_id": None,
            "device_config": None,
        },
        None,
        None,
    )

    assert mqtt_cover.find_percentage_in_range(120) == 40
    assert mqtt_cover.find_percentage_in_range(120, "cover") == 40


async def test_find_percentage_in_range_defaults_inverted(hass):
    """Test find percentage in range with default range but inverted."""
    mqtt_cover = MqttCover(
        hass,
        {
            "name": "cover.test",
            "state_topic": "state-topic",
            "get_position_topic": None,
            "command_topic": "command-topic",
            "availability_topic": None,
            "tilt_command_topic": "tilt-command-topic",
            "tilt_status_topic": "tilt-status-topic",
            "qos": 0,
            "retain": False,
            "state_open": "OPEN",
            "state_closed": "CLOSE",
            "position_open": 0,
            "position_closed": 100,
            "payload_open": "OPEN",
            "payload_close": "CLOSE",
            "payload_stop": "STOP",
            "payload_available": None,
            "payload_not_available": None,
            "optimistic": False,
            "value_template": None,
            "tilt_open_position": 100,
            "tilt_closed_position": 0,
            "tilt_min": 100,
            "tilt_max": 0,
            "tilt_optimistic": False,
            "set_position_topic": None,
            "set_position_template": None,
            "unique_id": None,
            "device_config": None,
        },
        None,
        None,
    )

    assert mqtt_cover.find_percentage_in_range(44) == 56
    assert mqtt_cover.find_percentage_in_range(44, "cover") == 56


async def test_find_percentage_in_range_altered_inverted(hass):
    """Test find percentage in range with altered range and inverted."""
    mqtt_cover = MqttCover(
        hass,
        {
            "name": "cover.test",
            "state_topic": "state-topic",
            "get_position_topic": None,
            "command_topic": "command-topic",
            "availability_topic": None,
            "tilt_command_topic": "tilt-command-topic",
            "tilt_status_topic": "tilt-status-topic",
            "qos": 0,
            "retain": False,
            "state_open": "OPEN",
            "state_closed": "CLOSE",
            "position_open": 80,
            "position_closed": 180,
            "payload_open": "OPEN",
            "payload_close": "CLOSE",
            "payload_stop": "STOP",
            "payload_available": None,
            "payload_not_available": None,
            "optimistic": False,
            "value_template": None,
            "tilt_open_position": 180,
            "tilt_closed_position": 80,
            "tilt_min": 180,
            "tilt_max": 80,
            "tilt_optimistic": False,
            "set_position_topic": None,
            "set_position_template": None,
            "unique_id": None,
            "device_config": None,
        },
        None,
        None,
    )

    assert mqtt_cover.find_percentage_in_range(120) == 60
    assert mqtt_cover.find_percentage_in_range(120, "cover") == 60


async def test_find_in_range_defaults(hass):
    """Test find in range with default range."""
    mqtt_cover = MqttCover(
        hass,
        {
            "name": "cover.test",
            "state_topic": "state-topic",
            "get_position_topic": None,
            "command_topic": "command-topic",
            "availability_topic": None,
            "tilt_command_topic": "tilt-command-topic",
            "tilt_status_topic": "tilt-status-topic",
            "qos": 0,
            "retain": False,
            "state_open": "OPEN",
            "state_closed": "CLOSE",
            "position_open": 100,
            "position_closed": 0,
            "payload_open": "OPEN",
            "payload_close": "CLOSE",
            "payload_stop": "STOP",
            "payload_available": None,
            "payload_not_available": None,
            "optimistic": False,
            "value_template": None,
            "tilt_open_position": 100,
            "tilt_closed_position": 0,
            "tilt_min": 0,
            "tilt_max": 100,
            "tilt_optimistic": False,
            "set_position_topic": None,
            "set_position_template": None,
            "unique_id": None,
            "device_config": None,
        },
        None,
        None,
    )

    assert mqtt_cover.find_in_range_from_percent(44) == 44
    assert mqtt_cover.find_in_range_from_percent(44, "cover") == 44


async def test_find_in_range_altered(hass):
    """Test find in range with altered range."""
    mqtt_cover = MqttCover(
        hass,
        {
            "name": "cover.test",
            "state_topic": "state-topic",
            "get_position_topic": None,
            "command_topic": "command-topic",
            "availability_topic": None,
            "tilt_command_topic": "tilt-command-topic",
            "tilt_status_topic": "tilt-status-topic",
            "qos": 0,
            "retain": False,
            "state_open": "OPEN",
            "state_closed": "CLOSE",
            "position_open": 180,
            "position_closed": 80,
            "payload_open": "OPEN",
            "payload_close": "CLOSE",
            "payload_stop": "STOP",
            "payload_available": None,
            "payload_not_available": None,
            "optimistic": False,
            "value_template": None,
            "tilt_open_position": 180,
            "tilt_closed_position": 80,
            "tilt_min": 80,
            "tilt_max": 180,
            "tilt_optimistic": False,
            "set_position_topic": None,
            "set_position_template": None,
            "unique_id": None,
            "device_config": None,
        },
        None,
        None,
    )

    assert mqtt_cover.find_in_range_from_percent(40) == 120
    assert mqtt_cover.find_in_range_from_percent(40, "cover") == 120


async def test_find_in_range_defaults_inverted(hass):
    """Test find in range with default range but inverted."""
    mqtt_cover = MqttCover(
        hass,
        {
            "name": "cover.test",
            "state_topic": "state-topic",
            "get_position_topic": None,
            "command_topic": "command-topic",
            "availability_topic": None,
            "tilt_command_topic": "tilt-command-topic",
            "tilt_status_topic": "tilt-status-topic",
            "qos": 0,
            "retain": False,
            "state_open": "OPEN",
            "state_closed": "CLOSE",
            "position_open": 0,
            "position_closed": 100,
            "payload_open": "OPEN",
            "payload_close": "CLOSE",
            "payload_stop": "STOP",
            "payload_available": None,
            "payload_not_available": None,
            "optimistic": False,
            "value_template": None,
            "tilt_open_position": 100,
            "tilt_closed_position": 0,
            "tilt_min": 100,
            "tilt_max": 0,
            "tilt_optimistic": False,
            "set_position_topic": None,
            "set_position_template": None,
            "unique_id": None,
            "device_config": None,
        },
        None,
        None,
    )

    assert mqtt_cover.find_in_range_from_percent(56) == 44
    assert mqtt_cover.find_in_range_from_percent(56, "cover") == 44


async def test_find_in_range_altered_inverted(hass):
    """Test find in range with altered range and inverted."""
    mqtt_cover = MqttCover(
        hass,
        {
            "name": "cover.test",
            "state_topic": "state-topic",
            "get_position_topic": None,
            "command_topic": "command-topic",
            "availability_topic": None,
            "tilt_command_topic": "tilt-command-topic",
            "tilt_status_topic": "tilt-status-topic",
            "qos": 0,
            "retain": False,
            "state_open": "OPEN",
            "state_closed": "CLOSE",
            "position_open": 80,
            "position_closed": 180,
            "payload_open": "OPEN",
            "payload_close": "CLOSE",
            "payload_stop": "STOP",
            "payload_available": None,
            "payload_not_available": None,
            "optimistic": False,
            "value_template": None,
            "tilt_open_position": 180,
            "tilt_closed_position": 80,
            "tilt_min": 180,
            "tilt_max": 80,
            "tilt_optimistic": False,
            "set_position_topic": None,
            "set_position_template": None,
            "unique_id": None,
            "device_config": None,
        },
        None,
        None,
    )

    assert mqtt_cover.find_in_range_from_percent(60) == 120
    assert mqtt_cover.find_in_range_from_percent(60, "cover") == 120


async def test_availability_when_connection_lost(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry_with_yaml_config, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(hass, mqtt_mock_entry_with_yaml_config):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry_with_yaml_config, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock_entry_with_yaml_config):
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(hass, mqtt_mock_entry_with_yaml_config):
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_valid_device_class(hass, mqtt_mock_entry_with_yaml_config):
    """Test the setting of a valid device class."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "device_class": "garage",
                "state_topic": "test-topic",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.attributes.get("device_class") == "garage"


async def test_invalid_device_class(hass, mqtt_mock_entry_no_yaml_config):
    """Test the setting of an invalid device class."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "device_class": "abc123",
                "state_topic": "test-topic",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    state = hass.states.get("cover.test")
    assert state is None


async def test_setting_attribute_via_mqtt_json_message(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry_with_yaml_config, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        cover.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_COVER_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(hass, mqtt_mock_entry_with_yaml_config):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry_with_yaml_config, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry_with_yaml_config, caplog, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_json(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock_entry_with_yaml_config, caplog, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry_no_yaml_config, caplog, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass, mqtt_mock_entry_with_yaml_config):
    """Test unique_id option only creates one cover per id."""
    config = {
        cover.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "state_topic": "test-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "state_topic": "test-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(
        hass, mqtt_mock_entry_with_yaml_config, cover.DOMAIN, config
    )


async def test_discovery_removal_cover(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test removal of discovered cover."""
    data = '{ "name": "test", "command_topic": "test_topic" }'
    await help_test_discovery_removal(
        hass, mqtt_mock_entry_no_yaml_config, caplog, cover.DOMAIN, data
    )


async def test_discovery_update_cover(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test update of discovered cover."""
    config1 = {"name": "Beer", "command_topic": "test_topic"}
    config2 = {"name": "Milk", "command_topic": "test_topic"}
    await help_test_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, caplog, cover.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_cover(
    hass, mqtt_mock_entry_no_yaml_config, caplog
):
    """Test update of discovered cover."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic" }'
    with patch(
        "homeassistant.components.mqtt.cover.MqttCover.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry_no_yaml_config,
            caplog,
            cover.DOMAIN,
            data1,
            discovery_update,
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic#" }'
    data2 = '{ "name": "Milk", "command_topic": "test_topic" }'
    await help_test_discovery_broken(
        hass, mqtt_mock_entry_no_yaml_config, caplog, cover.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT cover device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry_no_yaml_config, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT cover device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry_no_yaml_config, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock_entry_no_yaml_config):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry_no_yaml_config, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock_entry_no_yaml_config):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry_no_yaml_config, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock_entry_with_yaml_config):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry_with_yaml_config, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        cover.DOMAIN,
        DEFAULT_CONFIG,
        SERVICE_OPEN_COVER,
        command_payload="OPEN",
    )


async def test_state_and_position_topics_state_not_set_via_position_topic(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test state is not set via position topic when both state and position topics are set."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "position_topic": "get-position-topic",
                "position_open": 100,
                "position_closed": 0,
                "state_open": "OPEN",
                "state_closed": "CLOSE",
                "command_topic": "command-topic",
                "qos": 0,
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "OPEN")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "get-position-topic", "0")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "get-position-topic", "100")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "state-topic", "CLOSE")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED

    async_fire_mqtt_message(hass, "get-position-topic", "0")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED

    async_fire_mqtt_message(hass, "get-position-topic", "100")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED


async def test_set_state_via_position_using_stopped_state(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test the controlling state via position topic using stopped state."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "position_topic": "get-position-topic",
                "position_open": 100,
                "position_closed": 0,
                "state_open": "OPEN",
                "state_closed": "CLOSE",
                "state_stopped": "STOPPED",
                "command_topic": "command-topic",
                "qos": 0,
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "OPEN")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "get-position-topic", "0")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "state-topic", "STOPPED")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED

    async_fire_mqtt_message(hass, "get-position-topic", "100")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED

    async_fire_mqtt_message(hass, "state-topic", "STOPPED")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN


async def test_position_via_position_topic_template(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test position by updating status via position template."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "set_position_topic": "set-position-topic",
                "position_topic": "get-position-topic",
                "position_template": "{{ (value | multiply(0.01)) | int }}",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "get-position-topic", "99")

    current_cover_position_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position_position == 0

    async_fire_mqtt_message(hass, "get-position-topic", "5000")

    current_cover_position_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position_position == 50


async def test_position_via_position_topic_template_json_value(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test position by updating status via position template with a JSON value."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "set_position_topic": "set-position-topic",
                "position_topic": "get-position-topic",
                "position_template": "{{ value_json.Var1 }}",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "get-position-topic", '{"Var1": 9, "Var2": 60}')

    current_cover_position_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position_position == 9

    async_fire_mqtt_message(hass, "get-position-topic", '{"Var1": 50, "Var2": 10}')

    current_cover_position_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position_position == 50

    async_fire_mqtt_message(hass, "get-position-topic", '{"Var2": 60}')

    assert (
        "Template variable warning: 'dict object' has no attribute 'Var1' when rendering"
    ) in caplog.text


async def test_position_template_with_entity_id(hass, mqtt_mock_entry_with_yaml_config):
    """Test position by updating status via position template."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "set_position_topic": "set-position-topic",
                "position_topic": "get-position-topic",
                "position_template": '\
                {% if state_attr(entity_id, "current_position") != None %}\
                    {{ value | int + state_attr(entity_id, "current_position") }} \
                {% else %} \
                    {{ value }} \
                {% endif %}',
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "get-position-topic", "10")

    current_cover_position_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position_position == 10

    async_fire_mqtt_message(hass, "get-position-topic", "10")

    current_cover_position_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position_position == 20


async def test_position_via_position_topic_template_return_json(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test position by updating status via position template and returning json."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "set_position_topic": "set-position-topic",
                "position_topic": "get-position-topic",
                "position_template": '{{ {"position" : value} | tojson }}',
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "get-position-topic", "55")

    current_cover_position_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position_position == 55


async def test_position_via_position_topic_template_return_json_warning(
    hass, caplog, mqtt_mock_entry_with_yaml_config
):
    """Test position by updating status via position template returning json without position attribute."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "set_position_topic": "set-position-topic",
                "position_topic": "get-position-topic",
                "position_template": '{{ {"pos" : value} | tojson }}',
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "get-position-topic", "55")

    assert (
        "Template (position_template) returned JSON without position attribute"
        in caplog.text
    )


async def test_position_and_tilt_via_position_topic_template_return_json(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test position and tilt by updating the position via position template."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "set_position_topic": "set-position-topic",
                "position_topic": "get-position-topic",
                "position_template": '\
                {{ {"position" : value, "tilt_position" : (value | int / 2)| int } | tojson }}',
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "get-position-topic", "0")

    current_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    current_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_position == 0 and current_tilt_position == 0

    async_fire_mqtt_message(hass, "get-position-topic", "99")
    current_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    current_tilt_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_position == 99 and current_tilt_position == 49


async def test_position_via_position_topic_template_all_variables(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test position by updating status via position template."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "set_position_topic": "set-position-topic",
                "position_topic": "get-position-topic",
                "tilt_command_topic": "tilt-command-topic",
                "position_open": 99,
                "position_closed": 1,
                "tilt_min": 11,
                "tilt_max": 22,
                "position_template": "\
                {% if value | int < tilt_max %}\
                    {{ tilt_min }}\
                {% endif %}\
                {% if value | int > position_closed %}\
                    {{ position_open }}\
                {% endif %}",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "get-position-topic", "0")

    current_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position == 10

    async_fire_mqtt_message(hass, "get-position-topic", "55")
    current_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position == 100


async def test_set_state_via_stopped_state_no_position_topic(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test the controlling state via stopped state when no position topic."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "state_open": "OPEN",
                "state_closed": "CLOSE",
                "state_stopped": "STOPPED",
                "state_opening": "OPENING",
                "state_closing": "CLOSING",
                "command_topic": "command-topic",
                "qos": 0,
                "optimistic": False,
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "state-topic", "OPEN")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "state-topic", "OPENING")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPENING

    async_fire_mqtt_message(hass, "state-topic", "STOPPED")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "state-topic", "CLOSING")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSING

    async_fire_mqtt_message(hass, "state-topic", "STOPPED")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED


async def test_position_via_position_topic_template_return_invalid_json(
    hass, caplog, mqtt_mock_entry_with_yaml_config
):
    """Test position by updating status via position template and returning invalid json."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "set_position_topic": "set-position-topic",
                "position_topic": "get-position-topic",
                "position_template": '{{ {"position" : invalid_json} }}',
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "get-position-topic", "55")

    assert ("Payload '{'position': Undefined}' is not numeric") in caplog.text


async def test_set_position_topic_without_get_position_topic_error(
    hass, caplog, mqtt_mock_entry_no_yaml_config
):
    """Test error when set_position_topic is used without position_topic."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "set_position_topic": "set-position-topic",
                "value_template": "{{100-62}}",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    assert (
        f"'{CONF_SET_POSITION_TOPIC}' must be set together with '{CONF_GET_POSITION_TOPIC}'."
    ) in caplog.text


async def test_value_template_without_state_topic_error(
    hass, caplog, mqtt_mock_entry_no_yaml_config
):
    """Test error when value_template is used and state_topic is missing."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "value_template": "{{100-62}}",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    assert (
        f"'{CONF_VALUE_TEMPLATE}' must be set together with '{CONF_STATE_TOPIC}'."
    ) in caplog.text


async def test_position_template_without_position_topic_error(
    hass, caplog, mqtt_mock_entry_no_yaml_config
):
    """Test error when position_template is used and position_topic is missing."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "position_template": "{{100-52}}",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    assert (
        f"'{CONF_GET_POSITION_TEMPLATE}' must be set together with '{CONF_GET_POSITION_TOPIC}'."
        in caplog.text
    )


async def test_set_position_template_without_set_position_topic(
    hass, caplog, mqtt_mock_entry_no_yaml_config
):
    """Test error when set_position_template is used and set_position_topic is missing."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "set_position_template": "{{100-42}}",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    assert (
        f"'{CONF_SET_POSITION_TEMPLATE}' must be set together with '{CONF_SET_POSITION_TOPIC}'."
        in caplog.text
    )


async def test_tilt_command_template_without_tilt_command_topic(
    hass, caplog, mqtt_mock_entry_no_yaml_config
):
    """Test error when tilt_command_template is used and tilt_command_topic is missing."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "tilt_command_template": "{{100-32}}",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    assert (
        f"'{CONF_TILT_COMMAND_TEMPLATE}' must be set together with '{CONF_TILT_COMMAND_TOPIC}'."
        in caplog.text
    )


async def test_tilt_status_template_without_tilt_status_topic_topic(
    hass, caplog, mqtt_mock_entry_no_yaml_config
):
    """Test error when tilt_status_template is used and tilt_status_topic is missing."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "tilt_status_template": "{{100-22}}",
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    assert (
        f"'{CONF_TILT_STATUS_TEMPLATE}' must be set together with '{CONF_TILT_STATUS_TOPIC}'."
        in caplog.text
    )


@pytest.mark.parametrize(
    "service,topic,parameters,payload,template",
    [
        (
            SERVICE_OPEN_COVER,
            "command_topic",
            None,
            "OPEN",
            None,
        ),
        (
            SERVICE_SET_COVER_POSITION,
            "set_position_topic",
            {ATTR_POSITION: "50"},
            50,
            "set_position_template",
        ),
        (
            SERVICE_SET_COVER_TILT_POSITION,
            "tilt_command_topic",
            {ATTR_TILT_POSITION: "45"},
            45,
            "tilt_command_template",
        ),
    ],
)
async def test_publishing_with_custom_encoding(
    hass,
    mqtt_mock_entry_with_yaml_config,
    caplog,
    service,
    topic,
    parameters,
    payload,
    template,
):
    """Test publishing MQTT payload with different encoding."""
    domain = cover.DOMAIN
    config = DEFAULT_CONFIG[domain]
    config["position_topic"] = "some-position-topic"

    await help_test_publishing_with_custom_encoding(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        domain,
        config,
        service,
        topic,
        parameters,
        payload,
        template,
    )


async def test_reloadable(hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path):
    """Test reloading the MQTT platform."""
    domain = cover.DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_reloadable(
        hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path, domain, config
    )


async def test_reloadable_late(hass, mqtt_client_mock, caplog, tmp_path):
    """Test reloading the MQTT platform with late entry setup."""
    domain = cover.DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_reloadable_late(hass, caplog, tmp_path, domain, config)


@pytest.mark.parametrize(
    "topic,value,attribute,attribute_value",
    [
        ("state_topic", "open", None, None),
        ("state_topic", "closing", None, None),
        ("position_topic", "40", "current_position", 40),
        ("tilt_status_topic", "60", "current_tilt_position", 60),
    ],
)
async def test_encoding_subscribable_topics(
    hass,
    mqtt_mock_entry_with_yaml_config,
    caplog,
    topic,
    value,
    attribute,
    attribute_value,
):
    """Test handling of incoming encoded payload."""
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        cover.DOMAIN,
        DEFAULT_CONFIG[cover.DOMAIN],
        topic,
        value,
        attribute,
        attribute_value,
        skip_raw_test=True,
    )


async def test_setup_manual_entity_from_yaml(hass):
    """Test setup manual configured MQTT entity."""
    platform = cover.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG[platform])
    config["name"] = "test"
    del config["platform"]
    await help_test_setup_manual_entity_from_yaml(hass, platform, config)
    assert hass.states.get(f"{platform}.test") is not None


async def test_unload_entry(hass, mqtt_mock_entry_with_yaml_config, tmp_path):
    """Test unloading the config entry."""
    domain = cover.DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry_with_yaml_config, tmp_path, domain, config
    )
