"""The tests for the MQTT cover platform."""
import pytest

from homeassistant.components import cover
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
)
from homeassistant.components.mqtt.cover import MqttCover
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
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
    help_test_entity_debug_info_message,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_unique_id,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.async_mock import patch
from tests.common import async_fire_mqtt_message

DEFAULT_CONFIG = {
    cover.DOMAIN: {"platform": "mqtt", "name": "test", "state_topic": "test-topic"}
}


async def test_state_via_state_topic(hass, mqtt_mock):
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

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", STATE_CLOSED)

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED

    async_fire_mqtt_message(hass, "state-topic", STATE_OPEN)

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN


async def test_opening_and_closing_state_via_custom_state_payload(hass, mqtt_mock):
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


async def test_open_closed_state_from_position_optimistic(hass, mqtt_mock):
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


async def test_position_via_position_topic(hass, mqtt_mock):
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

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "get-position-topic", "0")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED

    async_fire_mqtt_message(hass, "get-position-topic", "100")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN


async def test_state_via_template(hass, mqtt_mock):
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

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "state-topic", "10000")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "state-topic", "99")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED


async def test_position_via_template(hass, mqtt_mock):
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
                "value_template": "{{ (value | multiply(0.01)) | int }}",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "get-position-topic", "10000")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "get-position-topic", "5000")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "get-position-topic", "99")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED


async def test_optimistic_state_change(hass, mqtt_mock):
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
    assert STATE_CLOSED == state.state

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OPEN", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("cover.test")
    assert STATE_OPEN == state.state

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "CLOSE", 0, False)
    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED


async def test_optimistic_state_change_with_position(hass, mqtt_mock):
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
    assert STATE_CLOSED == state.state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 0

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OPEN", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("cover.test")
    assert STATE_OPEN == state.state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 100

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "CLOSE", 0, False)
    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 0


async def test_send_open_cover_command(hass, mqtt_mock):
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

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OPEN", 2, False)
    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN


async def test_send_close_cover_command(hass, mqtt_mock):
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

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "CLOSE", 2, False)
    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN


async def test_send_stop__cover_command(hass, mqtt_mock):
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

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "STOP", 2, False)
    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN


async def test_current_cover_position(hass, mqtt_mock):
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

    state_attributes_dict = hass.states.get("cover.test").attributes
    assert not (ATTR_CURRENT_POSITION in state_attributes_dict)
    assert not (ATTR_CURRENT_TILT_POSITION in state_attributes_dict)
    assert not (4 & hass.states.get("cover.test").attributes["supported_features"] == 4)

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


async def test_current_cover_position_inverted(hass, mqtt_mock):
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

    state_attributes_dict = hass.states.get("cover.test").attributes
    assert not (ATTR_CURRENT_POSITION in state_attributes_dict)
    assert not (ATTR_CURRENT_TILT_POSITION in state_attributes_dict)
    assert not (4 & hass.states.get("cover.test").attributes["supported_features"] == 4)

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


async def test_optimistic_position(hass, mqtt_mock):
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

    state = hass.states.get("cover.test")
    assert state is None


async def test_position_update(hass, mqtt_mock):
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

    state_attributes_dict = hass.states.get("cover.test").attributes
    assert not (ATTR_CURRENT_POSITION in state_attributes_dict)
    assert not (ATTR_CURRENT_TILT_POSITION in state_attributes_dict)
    assert 4 & hass.states.get("cover.test").attributes["supported_features"] == 4

    async_fire_mqtt_message(hass, "get-position-topic", "22")
    state_attributes_dict = hass.states.get("cover.test").attributes
    assert ATTR_CURRENT_POSITION in state_attributes_dict
    assert not (ATTR_CURRENT_TILT_POSITION in state_attributes_dict)
    current_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position == 22


async def test_set_position_templated(hass, mqtt_mock):
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
                "set_position_template": "{{100-62}}",
                "payload_open": "OPEN",
                "payload_close": "CLOSE",
                "payload_stop": "STOP",
            }
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: 100},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "set-position-topic", "38", 0, False
    )


async def test_set_position_untemplated(hass, mqtt_mock):
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

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: 62},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("position-topic", 62, 0, False)


async def test_set_position_untemplated_custom_percentage_range(hass, mqtt_mock):
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

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: 38},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("position-topic", 62, 0, False)


async def test_no_command_topic(hass, mqtt_mock):
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

    assert hass.states.get("cover.test").attributes["supported_features"] == 240


async def test_no_payload_stop(hass, mqtt_mock):
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

    assert hass.states.get("cover.test").attributes["supported_features"] == 3


async def test_with_command_topic_and_tilt(hass, mqtt_mock):
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

    assert hass.states.get("cover.test").attributes["supported_features"] == 251


async def test_tilt_defaults(hass, mqtt_mock):
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

    state_attributes_dict = hass.states.get("cover.test").attributes
    assert ATTR_CURRENT_TILT_POSITION in state_attributes_dict

    current_cover_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_TILT_POSITION
    ]
    assert current_cover_position == STATE_UNKNOWN


async def test_tilt_via_invocation_defaults(hass, mqtt_mock):
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

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 100, 0, False)
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 0, 0, False)
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

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 100, 0, False)
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

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 0, 0, False)


async def test_tilt_given_value(hass, mqtt_mock):
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

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 80, 0, False)
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 25, 0, False)
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

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 80, 0, False)
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

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 25, 0, False)


async def test_tilt_given_value_optimistic(hass, mqtt_mock):
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

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 80, 0, False)
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

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 25, 0, False)


async def test_tilt_given_value_altered_range(hass, mqtt_mock):
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

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 25, 0, False)
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

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 0, 0, False)
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

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 25, 0, False)


async def test_tilt_via_topic(hass, mqtt_mock):
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


async def test_tilt_via_topic_template(hass, mqtt_mock):
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


async def test_tilt_via_topic_altered_range(hass, mqtt_mock):
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


async def test_tilt_via_topic_template_altered_range(hass, mqtt_mock):
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


async def test_tilt_position(hass, mqtt_mock):
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

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: 50},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 50, 0, False)


async def test_tilt_position_altered_range(hass, mqtt_mock):
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

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: 50},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("tilt-command-topic", 25, 0, False)


async def test_find_percentage_in_range_defaults(hass, mqtt_mock):
    """Test find percentage in range with default range."""
    mqtt_cover = MqttCover(
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
            "tilt_invert_state": False,
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


async def test_find_percentage_in_range_altered(hass, mqtt_mock):
    """Test find percentage in range with altered range."""
    mqtt_cover = MqttCover(
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
            "tilt_invert_state": False,
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


async def test_find_percentage_in_range_defaults_inverted(hass, mqtt_mock):
    """Test find percentage in range with default range but inverted."""
    mqtt_cover = MqttCover(
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
            "tilt_min": 0,
            "tilt_max": 100,
            "tilt_optimistic": False,
            "tilt_invert_state": True,
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


async def test_find_percentage_in_range_altered_inverted(hass, mqtt_mock):
    """Test find percentage in range with altered range and inverted."""
    mqtt_cover = MqttCover(
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
            "tilt_min": 80,
            "tilt_max": 180,
            "tilt_optimistic": False,
            "tilt_invert_state": True,
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


async def test_find_in_range_defaults(hass, mqtt_mock):
    """Test find in range with default range."""
    mqtt_cover = MqttCover(
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
            "tilt_invert_state": False,
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


async def test_find_in_range_altered(hass, mqtt_mock):
    """Test find in range with altered range."""
    mqtt_cover = MqttCover(
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
            "tilt_invert_state": False,
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


async def test_find_in_range_defaults_inverted(hass, mqtt_mock):
    """Test find in range with default range but inverted."""
    mqtt_cover = MqttCover(
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
            "tilt_min": 0,
            "tilt_max": 100,
            "tilt_optimistic": False,
            "tilt_invert_state": True,
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


async def test_find_in_range_altered_inverted(hass, mqtt_mock):
    """Test find in range with altered range and inverted."""
    mqtt_cover = MqttCover(
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
            "tilt_min": 80,
            "tilt_max": 180,
            "tilt_optimistic": False,
            "tilt_invert_state": True,
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


async def test_availability_when_connection_lost(hass, mqtt_mock):
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_valid_device_class(hass, mqtt_mock):
    """Test the setting of a valid sensor class."""
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

    state = hass.states.get("cover.test")
    assert state.attributes.get("device_class") == "garage"


async def test_invalid_device_class(hass, mqtt_mock):
    """Test the setting of an invalid sensor class."""
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

    state = hass.states.get("cover.test")
    assert state is None


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_with_template(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass, mqtt_mock):
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
    await help_test_unique_id(hass, mqtt_mock, cover.DOMAIN, config)


async def test_discovery_removal_cover(hass, mqtt_mock, caplog):
    """Test removal of discovered cover."""
    data = '{ "name": "test", "command_topic": "test_topic" }'
    await help_test_discovery_removal(hass, mqtt_mock, caplog, cover.DOMAIN, data)


async def test_discovery_update_cover(hass, mqtt_mock, caplog):
    """Test update of discovered cover."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic" }'
    data2 = '{ "name": "Milk", "command_topic": "test_topic" }'
    await help_test_discovery_update(
        hass, mqtt_mock, caplog, cover.DOMAIN, data1, data2
    )


async def test_discovery_update_unchanged_cover(hass, mqtt_mock, caplog):
    """Test update of discovered cover."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic" }'
    with patch(
        "homeassistant.components.mqtt.cover.MqttCover.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock, caplog, cover.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic#" }'
    data2 = '{ "name": "Milk", "command_topic": "test_topic" }'
    await help_test_discovery_broken(
        hass, mqtt_mock, caplog, cover.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT cover device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT cover device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock):
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass, mqtt_mock, cover.DOMAIN, DEFAULT_CONFIG
    )
