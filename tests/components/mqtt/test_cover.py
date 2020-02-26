"""The tests for the MQTT cover platform."""
import json
from unittest.mock import ANY

from homeassistant.components import cover, mqtt
from homeassistant.components.cover import ATTR_POSITION, ATTR_TILT_POSITION
from homeassistant.components.mqtt.cover import MqttCover
from homeassistant.components.mqtt.discovery import async_start
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
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_mock_mqtt_component,
    mock_registry,
)


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

    state_attributes_dict = hass.states.get("cover.test").attributes
    assert not ("current_position" in state_attributes_dict)
    assert not ("current_tilt_position" in state_attributes_dict)
    assert not (4 & hass.states.get("cover.test").attributes["supported_features"] == 4)

    async_fire_mqtt_message(hass, "get-position-topic", "0")
    current_cover_position = hass.states.get("cover.test").attributes[
        "current_position"
    ]
    assert current_cover_position == 0

    async_fire_mqtt_message(hass, "get-position-topic", "50")
    current_cover_position = hass.states.get("cover.test").attributes[
        "current_position"
    ]
    assert current_cover_position == 50

    async_fire_mqtt_message(hass, "get-position-topic", "non-numeric")
    current_cover_position = hass.states.get("cover.test").attributes[
        "current_position"
    ]
    assert current_cover_position == 50

    async_fire_mqtt_message(hass, "get-position-topic", "101")
    current_cover_position = hass.states.get("cover.test").attributes[
        "current_position"
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

    state_attributes_dict = hass.states.get("cover.test").attributes
    assert not ("current_position" in state_attributes_dict)
    assert not ("current_tilt_position" in state_attributes_dict)
    assert not (4 & hass.states.get("cover.test").attributes["supported_features"] == 4)

    async_fire_mqtt_message(hass, "get-position-topic", "100")
    current_percentage_cover_position = hass.states.get("cover.test").attributes[
        "current_position"
    ]
    assert current_percentage_cover_position == 0
    assert hass.states.get("cover.test").state == STATE_CLOSED

    async_fire_mqtt_message(hass, "get-position-topic", "0")
    current_percentage_cover_position = hass.states.get("cover.test").attributes[
        "current_position"
    ]
    assert current_percentage_cover_position == 100
    assert hass.states.get("cover.test").state == STATE_OPEN

    async_fire_mqtt_message(hass, "get-position-topic", "50")
    current_percentage_cover_position = hass.states.get("cover.test").attributes[
        "current_position"
    ]
    assert current_percentage_cover_position == 50
    assert hass.states.get("cover.test").state == STATE_OPEN

    async_fire_mqtt_message(hass, "get-position-topic", "non-numeric")
    current_percentage_cover_position = hass.states.get("cover.test").attributes[
        "current_position"
    ]
    assert current_percentage_cover_position == 50
    assert hass.states.get("cover.test").state == STATE_OPEN

    async_fire_mqtt_message(hass, "get-position-topic", "101")
    current_percentage_cover_position = hass.states.get("cover.test").attributes[
        "current_position"
    ]
    assert current_percentage_cover_position == 0
    assert hass.states.get("cover.test").state == STATE_CLOSED


async def test_set_cover_position(hass, mqtt_mock):
    """Test setting cover position."""
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

    state_attributes_dict = hass.states.get("cover.test").attributes
    assert not ("current_position" in state_attributes_dict)
    assert not ("current_tilt_position" in state_attributes_dict)
    assert 4 & hass.states.get("cover.test").attributes["supported_features"] == 4

    async_fire_mqtt_message(hass, "get-position-topic", "22")
    state_attributes_dict = hass.states.get("cover.test").attributes
    assert "current_position" in state_attributes_dict
    assert not ("current_tilt_position" in state_attributes_dict)
    current_cover_position = hass.states.get("cover.test").attributes[
        "current_position"
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

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: 62},
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

    state_attributes_dict = hass.states.get("cover.test").attributes
    assert "current_tilt_position" in state_attributes_dict

    current_cover_position = hass.states.get("cover.test").attributes[
        "current_tilt_position"
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
        "current_tilt_position"
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
        "current_tilt_position"
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
        "current_tilt_position"
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
        "current_tilt_position"
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

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        "current_tilt_position"
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
        "current_tilt_position"
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

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        "current_tilt_position"
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
        "current_tilt_position"
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
        "current_tilt_position"
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

    async_fire_mqtt_message(hass, "tilt-status-topic", "0")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        "current_tilt_position"
    ]
    assert current_cover_tilt_position == 0

    async_fire_mqtt_message(hass, "tilt-status-topic", "50")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        "current_tilt_position"
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

    async_fire_mqtt_message(hass, "tilt-status-topic", "99")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        "current_tilt_position"
    ]
    assert current_cover_tilt_position == 0

    async_fire_mqtt_message(hass, "tilt-status-topic", "5000")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        "current_tilt_position"
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

    async_fire_mqtt_message(hass, "tilt-status-topic", "0")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        "current_tilt_position"
    ]
    assert current_cover_tilt_position == 0

    async_fire_mqtt_message(hass, "tilt-status-topic", "50")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        "current_tilt_position"
    ]
    assert current_cover_tilt_position == 100

    async_fire_mqtt_message(hass, "tilt-status-topic", "25")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        "current_tilt_position"
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

    async_fire_mqtt_message(hass, "tilt-status-topic", "99")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        "current_tilt_position"
    ]
    assert current_cover_tilt_position == 0

    async_fire_mqtt_message(hass, "tilt-status-topic", "5000")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        "current_tilt_position"
    ]
    assert current_cover_tilt_position == 100

    async_fire_mqtt_message(hass, "tilt-status-topic", "2500")

    current_cover_tilt_position = hass.states.get("cover.test").attributes[
        "current_tilt_position"
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


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
            }
        },
    )

    state = hass.states.get("cover.test")
    assert state.state != STATE_UNAVAILABLE


async def test_availability_by_defaults(hass, mqtt_mock):
    """Test availability by defaults with defined topic."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "availability_topic": "availability-topic",
            }
        },
    )

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "online")
    await hass.async_block_till_done()

    state = hass.states.get("cover.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "offline")
    await hass.async_block_till_done()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNAVAILABLE


async def test_availability_by_custom_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "availability_topic": "availability-topic",
                "payload_available": "good",
                "payload_not_available": "nogood",
            }
        },
    )

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "good")
    await hass.async_block_till_done()

    state = hass.states.get("cover.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "nogood")
    await hass.async_block_till_done()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNAVAILABLE


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

    state = hass.states.get("cover.test")
    assert state is None


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "json_attributes_topic": "attr-topic",
            }
        },
    )

    async_fire_mqtt_message(hass, "attr-topic", '{ "val": "100" }')
    state = hass.states.get("cover.test")

    assert state.attributes.get("val") == "100"


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "json_attributes_topic": "attr-topic",
            }
        },
    )

    async_fire_mqtt_message(hass, "attr-topic", '[ "list", "of", "things"]')
    state = hass.states.get("cover.test")

    assert state.attributes.get("val") is None
    assert "JSON result was not a dictionary" in caplog.text


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "json_attributes_topic": "attr-topic",
            }
        },
    )

    async_fire_mqtt_message(hass, "attr-topic", "This is not JSON")

    state = hass.states.get("cover.test")
    assert state.attributes.get("val") is None
    assert "Erroneous JSON: This is not JSON" in caplog.text


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, "homeassistant", {}, entry)
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
    async_fire_mqtt_message(hass, "homeassistant/cover/bla/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "attr-topic1", '{ "val": "100" }')
    state = hass.states.get("cover.beer")
    assert state.attributes.get("val") == "100"

    # Change json_attributes_topic
    async_fire_mqtt_message(hass, "homeassistant/cover/bla/config", data2)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, "attr-topic1", '{ "val": "50" }')
    state = hass.states.get("cover.beer")
    assert state.attributes.get("val") == "100"

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, "attr-topic2", '{ "val": "75" }')
    state = hass.states.get("cover.beer")
    assert state.attributes.get("val") == "75"


async def test_discovery_removal_cover(hass, mqtt_mock, caplog):
    """Test removal of discovered cover."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, "homeassistant", {}, entry)
    data = '{ "name": "Beer",' '  "command_topic": "test_topic" }'
    async_fire_mqtt_message(hass, "homeassistant/cover/bla/config", data)
    await hass.async_block_till_done()
    state = hass.states.get("cover.beer")
    assert state is not None
    assert state.name == "Beer"
    async_fire_mqtt_message(hass, "homeassistant/cover/bla/config", "")
    await hass.async_block_till_done()
    state = hass.states.get("cover.beer")
    assert state is None


async def test_discovery_update_cover(hass, mqtt_mock, caplog):
    """Test update of discovered cover."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, "homeassistant", {}, entry)
    data1 = '{ "name": "Beer",' '  "command_topic": "test_topic" }'
    data2 = '{ "name": "Milk",' '  "command_topic": "test_topic" }'
    async_fire_mqtt_message(hass, "homeassistant/cover/bla/config", data1)
    await hass.async_block_till_done()
    state = hass.states.get("cover.beer")
    assert state is not None
    assert state.name == "Beer"

    async_fire_mqtt_message(hass, "homeassistant/cover/bla/config", data2)
    await hass.async_block_till_done()

    state = hass.states.get("cover.beer")
    assert state is not None
    assert state.name == "Milk"

    state = hass.states.get("cover.milk")
    assert state is None


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, "homeassistant", {}, entry)

    data1 = '{ "name": "Beer",' '  "command_topic": "test_topic#" }'
    data2 = '{ "name": "Milk",' '  "command_topic": "test_topic" }'

    async_fire_mqtt_message(hass, "homeassistant/cover/bla/config", data1)
    await hass.async_block_till_done()

    state = hass.states.get("cover.beer")
    assert state is None

    async_fire_mqtt_message(hass, "homeassistant/cover/bla/config", data2)
    await hass.async_block_till_done()

    state = hass.states.get("cover.milk")
    assert state is not None
    assert state.name == "Milk"
    state = hass.states.get("cover.beer")
    assert state is None


async def test_unique_id(hass):
    """Test unique_id option only creates one cover per id."""
    await async_mock_mqtt_component(hass)
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
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
        },
    )

    async_fire_mqtt_message(hass, "test-topic", "payload")

    assert len(hass.states.async_entity_ids(cover.DOMAIN)) == 1


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT cover device registry integration."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps(
        {
            "platform": "mqtt",
            "name": "Test 1",
            "state_topic": "test-topic",
            "command_topic": "test-command-topic",
            "device": {
                "identifiers": ["helloworld"],
                "connections": [["mac", "02:5b:26:a8:dc:12"]],
                "manufacturer": "Whatever",
                "name": "Beer",
                "model": "Glass",
                "sw_version": "0.1-beta",
            },
            "unique_id": "veryunique",
        }
    )
    async_fire_mqtt_message(hass, "homeassistant/cover/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")}, set())
    assert device is not None
    assert device.identifiers == {("mqtt", "helloworld")}
    assert device.connections == {("mac", "02:5b:26:a8:dc:12")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.sw_version == "0.1-beta"


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    config = {
        "platform": "mqtt",
        "name": "Test 1",
        "state_topic": "test-topic",
        "command_topic": "test-command-topic",
        "device": {
            "identifiers": ["helloworld"],
            "connections": [["mac", "02:5b:26:a8:dc:12"]],
            "manufacturer": "Whatever",
            "name": "Beer",
            "model": "Glass",
            "sw_version": "0.1-beta",
        },
        "unique_id": "veryunique",
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/cover/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")}, set())
    assert device is not None
    assert device.name == "Beer"

    config["device"]["name"] = "Milk"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/cover/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")}, set())
    assert device is not None
    assert device.name == "Milk"


async def test_entity_id_update(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    registry = mock_registry(hass, {})
    mock_mqtt = await async_mock_mqtt_component(hass)
    assert await async_setup_component(
        hass,
        cover.DOMAIN,
        {
            cover.DOMAIN: [
                {
                    "platform": "mqtt",
                    "name": "beer",
                    "state_topic": "test-topic",
                    "availability_topic": "avty-topic",
                    "unique_id": "TOTALLY_UNIQUE",
                }
            ]
        },
    )

    state = hass.states.get("cover.beer")
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call("test-topic", ANY, 0, "utf-8")
    mock_mqtt.async_subscribe.assert_any_call("avty-topic", ANY, 0, "utf-8")
    mock_mqtt.async_subscribe.reset_mock()

    registry.async_update_entity("cover.beer", new_entity_id="cover.milk")
    await hass.async_block_till_done()

    state = hass.states.get("cover.beer")
    assert state is None

    state = hass.states.get("cover.milk")
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call("test-topic", ANY, 0, "utf-8")
    mock_mqtt.async_subscribe.assert_any_call("avty-topic", ANY, 0, "utf-8")
