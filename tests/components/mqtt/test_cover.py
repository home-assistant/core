"""The tests for the MQTT cover platform."""
from copy import deepcopy
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import cover, mqtt
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
from homeassistant.core import HomeAssistant

from .test_common import (
    help_custom_config,
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
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
    help_test_skipped_async_ha_write_state,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {cover.DOMAIN: {"name": "test", "state_topic": "test-topic"}}
}


@pytest.fixture(autouse=True)
def cover_platform_only():
    """Only setup the cover platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.COVER]):
        yield


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "qos": 0,
                    "payload_open": "OPEN",
                    "payload_close": "CLOSE",
                    "payload_stop": "STOP",
                }
            }
        }
    ],
)
async def test_state_via_state_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling state via topic."""
    await mqtt_mock_entry()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", STATE_CLOSED)

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED

    async_fire_mqtt_message(hass, "state-topic", STATE_OPEN)

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_opening_and_closing_state_via_custom_state_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling opening and closing state via a custom payload."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "position_topic": "position-topic",
                    "set_position_topic": "set-position-topic",
                    "qos": 0,
                    "payload_open": "OPEN",
                    "payload_close": "CLOSE",
                    "payload_stop": "STOP",
                    "optimistic": True,
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("position", "assert_state"),
    [
        (0, STATE_CLOSED),
        (1, STATE_OPEN),
        (30, STATE_OPEN),
        (99, STATE_OPEN),
        (100, STATE_OPEN),
    ],
)
async def test_open_closed_state_from_position_optimistic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    position: int,
    assert_state: str,
) -> None:
    """Test the state after setting the position using optimistic mode."""
    await mqtt_mock_entry()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: position},
        blocking=True,
    )

    state = hass.states.get("cover.test")
    assert state.state == assert_state
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(ATTR_CURRENT_POSITION) == position


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "position_topic": "position-topic",
                    "set_position_topic": "set-position-topic",
                    "qos": 0,
                    "payload_open": "OPEN",
                    "payload_close": "CLOSE",
                    "payload_stop": "STOP",
                    "optimistic": True,
                    "position_closed": 10,
                    "position_open": 90,
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("position", "assert_state"),
    [
        (0, STATE_CLOSED),
        (1, STATE_CLOSED),
        (10, STATE_CLOSED),
        (11, STATE_OPEN),
        (30, STATE_OPEN),
        (99, STATE_OPEN),
        (100, STATE_OPEN),
    ],
)
async def test_open_closed_state_from_position_optimistic_alt_positions(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    position: int,
    assert_state: str,
) -> None:
    """Test the state after setting the position.

    Test with alt opened and closed positions using optimistic mode.
    """
    await mqtt_mock_entry()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: position},
        blocking=True,
    )

    state = hass.states.get("cover.test")
    assert state.state == assert_state
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(ATTR_CURRENT_POSITION) == position


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "tilt_command_topic": "set-position-topic",
                    "qos": 0,
                    "payload_open": "OPEN",
                    "payload_close": "CLOSE",
                    "payload_stop": "STOP",
                    "optimistic": True,
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("tilt_position", "tilt_toggled_position"),
    [(0, 100), (1, 0), (99, 0), (100, 0)],
)
async def test_tilt_open_closed_toggle_optimistic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    tilt_position: int,
    tilt_toggled_position: int,
) -> None:
    """Test the tilt state after setting and toggling the tilt position.

    Test opened and closed tilt positions using optimistic mode.
    """
    await mqtt_mock_entry()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: tilt_position},
        blocking=True,
    )

    state = hass.states.get("cover.test")
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(ATTR_CURRENT_TILT_POSITION) == tilt_position

    # toggle cover tilt
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_TOGGLE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    state = hass.states.get("cover.test")
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(ATTR_CURRENT_TILT_POSITION) == tilt_toggled_position


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "tilt_command_topic": "set-position-topic",
                    "qos": 0,
                    "payload_open": "OPEN",
                    "payload_close": "CLOSE",
                    "payload_stop": "STOP",
                    "optimistic": True,
                    "tilt_min": 5,
                    "tilt_max": 95,
                    "tilt_closed_value": 15,
                    "tilt_opened_value": 85,
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("tilt_position", "tilt_toggled_position"),
    [(0, 88), (11, 88), (12, 11), (30, 11), (90, 11), (100, 11)],
)
async def test_tilt_open_closed_toggle_optimistic_alt_positions(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    tilt_position: int,
    tilt_toggled_position: int,
) -> None:
    """Test the tilt state after setting and toggling the tilt position.

    Test with alt opened and closed tilt positions using optimistic mode.
    """
    await mqtt_mock_entry()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: tilt_position},
        blocking=True,
    )

    state = hass.states.get("cover.test")
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(ATTR_CURRENT_TILT_POSITION) == tilt_position

    # toggle cover tilt
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_TOGGLE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test"},
        blocking=True,
    )

    state = hass.states.get("cover.test")
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(ATTR_CURRENT_TILT_POSITION) == tilt_toggled_position


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_position_via_position_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling state via topic."""
    await mqtt_mock_entry()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "get-position-topic", "0")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED

    async_fire_mqtt_message(hass, "get-position-topic", "100")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_state_via_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling state via topic."""
    await mqtt_mock_entry()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "state-topic", "10000")

    state = hass.states.get("cover.test")
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "state-topic", "99")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_state_via_template_and_entity_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling state via topic."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "qos": 0,
                    "value_template": "{{ value_json.Var1 }}",
                }
            }
        }
    ],
)
async def test_state_via_template_with_json_value(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the controlling state via topic with JSON value."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_position_via_template_and_entity_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling state via topic."""
    await mqtt_mock_entry()

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
    ("hass_config", "assumed_state"),
    [
        (
            {
                mqtt.DOMAIN: {
                    cover.DOMAIN: {"name": "test", "qos": 0, "command_topic": "abc"}
                }
            },
            True,
        ),
        (
            {
                mqtt.DOMAIN: {
                    cover.DOMAIN: {
                        "name": "test",
                        "qos": 0,
                        "command_topic": "abc",
                        "state_topic": "abc",
                    }
                }
            },
            False,
        ),
        # ({"set_position_topic": "abc"}, True), - not a valid configuration
        (
            {
                mqtt.DOMAIN: {
                    cover.DOMAIN: {
                        "name": "test",
                        "qos": 0,
                        "set_position_topic": "abc",
                        "position_topic": "abc",
                    }
                }
            },
            False,
        ),
        (
            {
                mqtt.DOMAIN: {
                    cover.DOMAIN: {
                        "name": "test",
                        "qos": 0,
                        "tilt_command_topic": "abc",
                    }
                }
            },
            True,
        ),
        (
            {
                mqtt.DOMAIN: {
                    cover.DOMAIN: {
                        "name": "test",
                        "qos": 0,
                        "tilt_command_topic": "abc",
                        "tilt_status_topic": "abc",
                    }
                }
            },
            False,
        ),
    ],
)
async def test_optimistic_flag(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    assumed_state: bool,
) -> None:
    """Test assumed_state is set correctly."""
    await mqtt_mock_entry()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN
    if assumed_state:
        assert ATTR_ASSUMED_STATE in state.attributes
    else:
        assert ATTR_ASSUMED_STATE not in state.attributes


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "qos": 0,
                }
            }
        }
    ],
)
async def test_optimistic_state_change(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test changing state optimistically."""
    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "optimistic": True,
                    "command_topic": "command-topic",
                    "position_topic": "position-topic",
                    "qos": 0,
                }
            }
        }
    ],
)
async def test_optimistic_state_change_with_position(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test changing state optimistically."""
    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "qos": 2,
                }
            }
        }
    ],
)
async def test_send_open_cover_command(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending of open_cover."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OPEN", 2, False)
    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "qos": 2,
                }
            }
        }
    ],
)
async def test_send_close_cover_command(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending of close_cover."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "CLOSE", 2, False)
    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "qos": 2,
                }
            }
        }
    ],
)
async def test_send_stop_cover_command(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending of stop_cover."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "STOP", 2, False)
    state = hass.states.get("cover.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "position_topic": "get-position-topic",
                    "command_topic": "command-topic",
                    "position_open": 100,
                    "position_closed": 0,
                    "payload_open": "OPEN",
                    "payload_close": "CLOSE",
                    "payload_stop": "STOP",
                }
            }
        }
    ],
)
async def test_current_cover_position(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the current cover position."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "position_topic": "get-position-topic",
                    "command_topic": "command-topic",
                    "position_open": 0,
                    "position_closed": 100,
                    "payload_open": "OPEN",
                    "payload_close": "CLOSE",
                    "payload_stop": "STOP",
                }
            }
        }
    ],
)
async def test_current_cover_position_inverted(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the current cover position."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "set_position_topic": "set-position-topic",
                }
            }
        }
    ],
)
async def test_optimistic_position(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test optimistic position is not supported."""
    assert await mqtt_mock_entry()
    assert (
        "'set_position_topic' must be set together with 'position_topic'" in caplog.text
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_position_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test cover position update from received MQTT message."""
    await mqtt_mock_entry()

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
    ("hass_config", "pos_call", "pos_message"),
    [
        (
            {
                mqtt.DOMAIN: {
                    cover.DOMAIN: {
                        "name": "test",
                        "position_topic": "get-position-topic",
                        "command_topic": "command-topic",
                        "position_open": 100,
                        "position_closed": 0,
                        "set_position_topic": "set-position-topic",
                        "set_position_template": "{{position-1}}",
                        "payload_open": "OPEN",
                        "payload_close": "CLOSE",
                        "payload_stop": "STOP",
                    }
                }
            },
            43,
            "42",
        ),
        (
            {
                mqtt.DOMAIN: {
                    cover.DOMAIN: {
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
                }
            },
            100,
            "38",
        ),
    ],
)
async def test_set_position_templated(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    pos_call: int,
    pos_message: str,
) -> None:
    """Test setting cover position via template."""
    mqtt_mock = await mqtt_mock_entry()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: pos_call},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "set-position-topic", pos_message, 0, False
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_set_position_templated_and_attributes(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting cover position via template and using entities attributes."""
    mqtt_mock = await mqtt_mock_entry()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: 100},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("set-position-topic", "5", 0, False)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_set_tilt_templated(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting cover tilt position via template."""
    mqtt_mock = await mqtt_mock_entry()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: 41},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "42", 0, False
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_set_tilt_templated_and_attributes(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting cover tilt position via template and using entities attributes."""
    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "position_topic": "state-topic",
                    "command_topic": "command-topic",
                    "set_position_topic": "position-topic",
                    "payload_open": "OPEN",
                    "payload_close": "CLOSE",
                    "payload_stop": "STOP",
                }
            }
        }
    ],
)
async def test_set_position_untemplated(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting cover position via template."""
    mqtt_mock = await mqtt_mock_entry()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: 62},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("position-topic", "62", 0, False)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_set_position_untemplated_custom_percentage_range(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting cover position via template."""
    mqtt_mock = await mqtt_mock_entry()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_POSITION: 38},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("position-topic", "62", 0, False)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "qos": 0,
                    "payload_open": "OPEN",
                    "payload_close": "CLOSE",
                    "payload_stop": "STOP",
                    "tilt_command_topic": "tilt-command",
                    "tilt_status_topic": "tilt-status",
                }
            }
        }
    ],
)
async def test_no_command_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test with no command topic."""
    await mqtt_mock_entry()

    assert hass.states.get("cover.test").attributes["supported_features"] == 240


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "qos": 0,
                    "payload_open": "OPEN",
                    "payload_close": None,
                    "payload_stop": "STOP",
                }
            }
        }
    ],
)
async def test_no_payload_close(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test with no close payload."""
    await mqtt_mock_entry()

    assert hass.states.get("cover.test").attributes["supported_features"] == 9


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "qos": 0,
                    "payload_open": None,
                    "payload_close": "CLOSE",
                    "payload_stop": "STOP",
                }
            }
        }
    ],
)
async def test_no_payload_open(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test with no open payload."""
    await mqtt_mock_entry()

    assert hass.states.get("cover.test").attributes["supported_features"] == 10


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "qos": 0,
                    "payload_open": "OPEN",
                    "payload_close": "CLOSE",
                    "payload_stop": None,
                }
            }
        }
    ],
)
async def test_no_payload_stop(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test with no stop payload."""
    await mqtt_mock_entry()

    assert hass.states.get("cover.test").attributes["supported_features"] == 3


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "command_topic": "test",
                    "name": "test",
                    "qos": 0,
                    "payload_open": "OPEN",
                    "payload_close": "CLOSE",
                    "payload_stop": "STOP",
                    "tilt_command_topic": "tilt-command",
                    "tilt_status_topic": "tilt-status",
                }
            }
        }
    ],
)
async def test_with_command_topic_and_tilt(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test with command topic and tilt config."""
    await mqtt_mock_entry()

    assert hass.states.get("cover.test").attributes["supported_features"] == 251


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_defaults(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the defaults."""
    await mqtt_mock_entry()

    state_attributes_dict = hass.states.get("cover.test").attributes
    # Tilt position is not yet known
    assert ATTR_CURRENT_TILT_POSITION not in state_attributes_dict


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_via_invocation_defaults(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test tilt defaults on close/open."""
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_given_value(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test tilting to a given value."""
    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_given_value_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test tilting to a given value."""
    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_given_value_altered_range(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test tilting to a given value."""
    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_via_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test tilt by updating status via MQTT."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_via_topic_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test tilt by updating status via MQTT and template."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_via_topic_template_json_value(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test tilt by updating status via MQTT and template with JSON value."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_via_topic_altered_range(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test tilt status via MQTT with altered tilt range."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_status_out_of_range_warning(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test tilt status via MQTT tilt out of range warning message."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "tilt-status-topic", "60")

    assert (
        "Payload '60' is out of range, must be between '0' and '50' inclusive"
    ) in caplog.text


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_status_not_numeric_warning(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test tilt status via MQTT tilt not numeric warning message."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "tilt-status-topic", "abc")

    assert ("Payload 'abc' is not numeric") in caplog.text


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_via_topic_altered_range_inverted(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test tilt status via MQTT with altered tilt range and inverted tilt position."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_via_topic_template_altered_range(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test tilt status via MQTT and template with altered tilt range."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_position(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test tilt via method invocation."""
    mqtt_mock = await mqtt_mock_entry()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: 50},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "50", 0, False
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_position_templated(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test tilt position via template."""
    mqtt_mock = await mqtt_mock_entry()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: 100},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "68", 0, False
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_tilt_position_altered_range(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test tilt via method invocation with altered range."""
    mqtt_mock = await mqtt_mock_entry()

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test", ATTR_TILT_POSITION: 50},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "tilt-command-topic", "25", 0, False
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, cover.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry, cover.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "device_class": "garage",
                    "state_topic": "test-topic",
                }
            }
        }
    ],
)
async def test_valid_device_class(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of a valid device class."""
    await mqtt_mock_entry()

    state = hass.states.get("cover.test")
    assert state.attributes.get("device_class") == "garage"


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "device_class": "abc123",
                    "state_topic": "test-topic",
                }
            }
        }
    ],
)
async def test_invalid_device_class(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test the setting of an invalid device class."""
    assert await mqtt_mock_entry()
    assert "expected CoverDeviceClass" in caplog.text


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry,
        cover.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_COVER_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass,
        mqtt_mock_entry,
        caplog,
        cover.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass,
        mqtt_mock_entry,
        caplog,
        cover.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_discovery_update_attr(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass,
        mqtt_mock_entry,
        caplog,
        cover.DOMAIN,
        DEFAULT_CONFIG,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: [
                    {
                        "name": "Test 1",
                        "state_topic": "test-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                    {
                        "name": "Test 2",
                        "state_topic": "test-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                ]
            }
        }
    ],
)
async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unique_id option only creates one cover per id."""
    await help_test_unique_id(hass, mqtt_mock_entry, cover.DOMAIN)


async def test_discovery_removal_cover(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal of discovered cover."""
    data = '{ "name": "test", "command_topic": "test_topic" }'
    await help_test_discovery_removal(hass, mqtt_mock_entry, caplog, cover.DOMAIN, data)


async def test_discovery_update_cover(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered cover."""
    config1 = {"name": "Beer", "command_topic": "test_topic"}
    config2 = {"name": "Milk", "command_topic": "test_topic"}
    await help_test_discovery_update(
        hass, mqtt_mock_entry, caplog, cover.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_cover(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered cover."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic" }'
    with patch(
        "homeassistant.components.mqtt.cover.MqttCover.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry,
            caplog,
            cover.DOMAIN,
            data1,
            discovery_update,
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic#" }'
    data2 = '{ "name": "Milk", "command_topic": "test_topic" }'
    await help_test_discovery_broken(
        hass, mqtt_mock_entry, caplog, cover.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT cover device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT cover device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, cover.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry,
        cover.DOMAIN,
        DEFAULT_CONFIG,
        SERVICE_OPEN_COVER,
        command_payload="OPEN",
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_state_and_position_topics_state_not_set_via_position_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test state is not set via position topic when both state and position topics are set."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_set_state_via_position_using_stopped_state(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling state via position topic using stopped state."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "set_position_topic": "set-position-topic",
                    "position_topic": "get-position-topic",
                    "position_template": "{{ (value | multiply(0.01)) | int }}",
                }
            }
        }
    ],
)
async def test_position_via_position_topic_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test position by updating status via position template."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "set_position_topic": "set-position-topic",
                    "position_topic": "get-position-topic",
                    "position_template": "{{ value_json.Var1 }}",
                }
            }
        }
    ],
)
async def test_position_via_position_topic_template_json_value(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test position by updating status via position template with a JSON value."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_position_template_with_entity_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test position by updating status via position template."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "set_position_topic": "set-position-topic",
                    "position_topic": "get-position-topic",
                    "position_template": '{{ {"position" : value} | tojson }}',
                }
            }
        }
    ],
)
async def test_position_via_position_topic_template_return_json(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test position by updating status via position template and returning json."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "get-position-topic", "55")

    current_cover_position_position = hass.states.get("cover.test").attributes[
        ATTR_CURRENT_POSITION
    ]
    assert current_cover_position_position == 55


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "set_position_topic": "set-position-topic",
                    "position_topic": "get-position-topic",
                    "position_template": '{{ {"pos" : value} | tojson }}',
                }
            }
        }
    ],
)
async def test_position_via_position_topic_template_return_json_warning(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test position by updating status via position template returning json without position attribute."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "get-position-topic", "55")

    assert (
        "Template (position_template) returned JSON without position attribute"
        in caplog.text
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "set_position_topic": "set-position-topic",
                    "position_topic": "get-position-topic",
                    "position_template": '\
                {{ {"position" : value, "tilt_position" : (value | int / 2)| int } | tojson }}',
                }
            }
        }
    ],
)
async def test_position_and_tilt_via_position_topic_template_return_json(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test position and tilt by updating the position via position template."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_position_via_position_topic_template_all_variables(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test position by updating status via position template."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
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
            }
        }
    ],
)
async def test_set_state_via_stopped_state_no_position_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling state via stopped state when no position topic."""
    await mqtt_mock_entry()

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

    async_fire_mqtt_message(hass, "state-topic", "STOPPED")

    state = hass.states.get("cover.test")
    assert state.state == STATE_CLOSED


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "set_position_topic": "set-position-topic",
                    "position_topic": "get-position-topic",
                    "position_template": '{{ {"position" : invalid_json} }}',
                }
            }
        }
    ],
)
async def test_position_via_position_topic_template_return_invalid_json(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test position by updating status via position template and returning invalid json."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "get-position-topic", "55")

    assert ("Payload '{'position': Undefined}' is not numeric") in caplog.text


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "set_position_topic": "set-position-topic",
                    "value_template": "{{100-62}}",
                }
            }
        }
    ],
)
async def test_set_position_topic_without_get_position_topic_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test error when set_position_topic is used without position_topic."""
    assert await mqtt_mock_entry()
    assert (
        f"'{CONF_SET_POSITION_TOPIC}' must be set together with '{CONF_GET_POSITION_TOPIC}'."
    ) in caplog.text


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "value_template": "{{100-62}}",
                }
            }
        }
    ],
)
async def test_value_template_without_state_topic_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test error when value_template is used and state_topic is missing."""
    assert await mqtt_mock_entry()
    assert (
        f"'{CONF_VALUE_TEMPLATE}' must be set together with '{CONF_STATE_TOPIC}'."
    ) in caplog.text


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "position_template": "{{100-52}}",
                }
            }
        }
    ],
)
async def test_position_template_without_position_topic_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test error when position_template is used and position_topic is missing."""
    assert await mqtt_mock_entry()
    assert (
        f"'{CONF_GET_POSITION_TEMPLATE}' must be set together with '{CONF_GET_POSITION_TOPIC}'."
        in caplog.text
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "set_position_template": "{{100-42}}",
                }
            }
        }
    ],
)
async def test_set_position_template_without_set_position_topic(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test error when set_position_template is used and set_position_topic is missing."""
    assert await mqtt_mock_entry()
    assert (
        f"'{CONF_SET_POSITION_TEMPLATE}' must be set together with '{CONF_SET_POSITION_TOPIC}'."
        in caplog.text
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "tilt_command_template": "{{100-32}}",
                }
            }
        }
    ],
)
async def test_tilt_command_template_without_tilt_command_topic(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test error when tilt_command_template is used and tilt_command_topic is missing."""
    assert await mqtt_mock_entry()
    assert (
        f"'{CONF_TILT_COMMAND_TEMPLATE}' must be set together with '{CONF_TILT_COMMAND_TOPIC}'."
        in caplog.text
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                cover.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "tilt_status_template": "{{100-22}}",
                }
            }
        }
    ],
)
async def test_tilt_status_template_without_tilt_status_topic_topic(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test error when tilt_status_template is used and tilt_status_topic is missing."""
    assert await mqtt_mock_entry()
    assert (
        f"'{CONF_TILT_STATUS_TEMPLATE}' must be set together with '{CONF_TILT_STATUS_TOPIC}'."
        in caplog.text
    )


@pytest.mark.parametrize(
    ("service", "topic", "parameters", "payload", "template"),
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
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    service: str,
    topic: str,
    parameters: dict[str, Any],
    payload: str,
    template: str | None,
) -> None:
    """Test publishing MQTT payload with different encoding."""
    domain = cover.DOMAIN
    config = deepcopy(DEFAULT_CONFIG)
    config[mqtt.DOMAIN][domain]["position_topic"] = "some-position-topic"

    await help_test_publishing_with_custom_encoding(
        hass,
        mqtt_mock_entry,
        caplog,
        domain,
        config,
        service,
        topic,
        parameters,
        payload,
        template,
    )


async def test_reloadable(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test reloading the MQTT platform."""
    domain = cover.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("state_topic", "open", None, None),
        ("state_topic", "closing", None, None),
        ("position_topic", "40", "current_position", 40),
        ("tilt_status_topic", "60", "current_tilt_position", 60),
    ],
)
async def test_encoding_subscribable_topics(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    topic: str,
    value: str,
    attribute: str | None,
    attribute_value: Any,
) -> None:
    """Test handling of incoming encoded payload."""
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry,
        cover.DOMAIN,
        DEFAULT_CONFIG[mqtt.DOMAIN][cover.DOMAIN],
        topic,
        value,
        attribute,
        attribute_value,
        skip_raw_test=True,
    )


@pytest.mark.parametrize(
    "hass_config",
    [DEFAULT_CONFIG, {"mqtt": [DEFAULT_CONFIG["mqtt"]]}],
    ids=["platform_key", "listed"],
)
async def test_setup_manual_entity_from_yaml(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setup manual configured MQTT entity."""
    await mqtt_mock_entry()
    platform = cover.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test unloading the config entry."""
    domain = cover.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            cover.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "availability_topic": "availability-topic",
                    "json_attributes_topic": "json-attributes-topic",
                    "state_topic": "test-topic",
                    "position_topic": "position-topic",
                    "tilt_status_topic": "tilt-status-topic",
                },
            ),
        )
    ],
)
@pytest.mark.parametrize(
    ("topic", "payload1", "payload2"),
    [
        ("test-topic", "open", "closed"),
        ("availability-topic", "online", "offline"),
        ("json-attributes-topic", '{"attr1": "val1"}', '{"attr1": "val2"}'),
        ("position-topic", "50", "100"),
        ("tilt-status-topic", "50", "100"),
    ],
)
async def test_skipped_async_ha_write_state(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    topic: str,
    payload1: str,
    payload2: str,
) -> None:
    """Test a write state command is only called when there is change."""
    await mqtt_mock_entry()
    await help_test_skipped_async_ha_write_state(hass, topic, payload1, payload2)
