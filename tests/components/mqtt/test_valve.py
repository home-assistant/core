"""The tests for the MQTT valve platform."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import mqtt, valve
from homeassistant.components.mqtt.valve import (
    MQTT_VALVE_ATTRIBUTES_BLOCKED,
    ValveEntityFeature,
)
from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    SERVICE_SET_VALVE_POSITION,
    ValveState,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_STOP_VALVE,
    STATE_UNKNOWN,
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
    mqtt.DOMAIN: {
        valve.DOMAIN: {
            "command_topic": "command-topic",
            "state_topic": "test-topic",
            "name": "test",
        }
    }
}

DEFAULT_CONFIG_REPORTS_POSITION = {
    mqtt.DOMAIN: {
        valve.DOMAIN: {
            "name": "test",
            "command_topic": "command-topic",
            "state_topic": "test-topic",
            "reports_position": True,
        }
    }
}


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("message", "asserted_state"),
    [
        ("open", ValveState.OPEN),
        ("closed", ValveState.CLOSED),
        ("closing", ValveState.CLOSING),
        ("opening", ValveState.OPENING),
        ('{"state" : "open"}', ValveState.OPEN),
        ('{"state" : "closed"}', ValveState.CLOSED),
        ('{"state" : "closing"}', ValveState.CLOSING),
        ('{"state" : "opening"}', ValveState.OPENING),
    ],
)
async def test_state_via_state_topic_no_position(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    message: str,
    asserted_state: str,
) -> None:
    """Test the controlling state via topic without position and without template."""
    await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", message)

    state = hass.states.get("valve.test")
    assert state.state == asserted_state

    async_fire_mqtt_message(hass, "state-topic", "None")

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "value_template": "{{ value_json.state }}",
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("message", "asserted_state"),
    [
        ('{"state":"open"}', ValveState.OPEN),
        ('{"state":"closed"}', ValveState.CLOSED),
        ('{"state":"closing"}', ValveState.CLOSING),
        ('{"state":"opening"}', ValveState.OPENING),
    ],
)
async def test_state_via_state_topic_with_template(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    message: str,
    asserted_state: str,
) -> None:
    """Test the controlling state via topic with template."""
    await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", message)

    state = hass.states.get("valve.test")
    assert state.state == asserted_state


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "reports_position": True,
                    "value_template": "{{ value_json.position }}",
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("message", "asserted_state"),
    [
        ('{"position":100}', ValveState.OPEN),
        ('{"position":50.0}', ValveState.OPEN),
        ('{"position":0}', ValveState.CLOSED),
        ('{"position":null}', STATE_UNKNOWN),
        ('{"position":"non_numeric"}', STATE_UNKNOWN),
        ('{"ignored":12}', STATE_UNKNOWN),
    ],
)
async def test_state_via_state_topic_with_position_template(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    message: str,
    asserted_state: str,
) -> None:
    """Test the controlling state via topic with position template."""
    await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", message)

    state = hass.states.get("valve.test")
    assert state.state == asserted_state


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "reports_position": True,
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("message", "asserted_state", "valve_position"),
    [
        ("invalid", STATE_UNKNOWN, None),
        ("0", ValveState.CLOSED, 0),
        ("opening", ValveState.OPENING, None),
        ("50", ValveState.OPEN, 50),
        ("closing", ValveState.CLOSING, None),
        ("100", ValveState.OPEN, 100),
        ("open", STATE_UNKNOWN, None),
        ("closed", STATE_UNKNOWN, None),
        ("-10", ValveState.CLOSED, 0),
        ("110", ValveState.OPEN, 100),
        ('{"position": 0, "state": "opening"}', ValveState.OPENING, 0),
        ('{"position": 10, "state": "opening"}', ValveState.OPENING, 10),
        ('{"position": 50, "state": "open"}', ValveState.OPEN, 50),
        ('{"position": 100, "state": "closing"}', ValveState.CLOSING, 100),
        ('{"position": 90, "state": "closing"}', ValveState.CLOSING, 90),
        ('{"position": 0, "state": "closed"}', ValveState.CLOSED, 0),
        ('{"position": -10, "state": "closed"}', ValveState.CLOSED, 0),
        ('{"position": 110, "state": "open"}', ValveState.OPEN, 100),
    ],
)
async def test_state_via_state_topic_through_position(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    message: str,
    asserted_state: str,
    valve_position: int | None,
) -> None:
    """Test the controlling state via topic through position.

    Test is still possible to process a `opening` or `closing` state update.
    Additional we test json messages can be processed containing both position and state.
    Incoming rendered positions are clamped between 0..100.
    """
    await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", message)

    state = hass.states.get("valve.test")
    assert state.state == asserted_state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == valve_position


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "reports_position": True,
                }
            }
        }
    ],
)
async def test_opening_closing_state_is_reset(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling state via topic through position.

    Test  a `opening` or `closing` state update is reset correctly after sequential updates.
    """
    await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    messages = [
        ('{"position": 0, "state": "opening"}', ValveState.OPENING, 0),
        ('{"position": 50, "state": "opening"}', ValveState.OPENING, 50),
        ('{"position": 60}', ValveState.OPENING, 60),
        ('{"position": 100, "state": "opening"}', ValveState.OPENING, 100),
        ('{"position": 100, "state": null}', ValveState.OPEN, 100),
        ('{"position": 90, "state": "closing"}', ValveState.CLOSING, 90),
        ('{"position": 40}', ValveState.CLOSING, 40),
        ('{"position": 0}', ValveState.CLOSED, 0),
        ('{"position": 10}', ValveState.OPEN, 10),
        ('{"position": 0, "state": "opening"}', ValveState.OPENING, 0),
        ('{"position": 0, "state": "closing"}', ValveState.CLOSING, 0),
        ('{"position": 0}', ValveState.CLOSED, 0),
    ]

    for message, asserted_state, valve_position in messages:
        async_fire_mqtt_message(hass, "state-topic", message)

        state = hass.states.get("valve.test")
        assert state.state == asserted_state
        assert state.attributes.get(ATTR_CURRENT_POSITION) == valve_position


@pytest.mark.parametrize(
    ("hass_config", "message", "err_message"),
    [
        (
            {
                mqtt.DOMAIN: {
                    valve.DOMAIN: {
                        "name": "test",
                        "state_topic": "state-topic",
                        "command_topic": "command-topic",
                        "reports_position": False,
                    }
                }
            },
            '{"position": 0}',
            "Missing required `state` attribute in json payload",
        ),
        (
            {
                mqtt.DOMAIN: {
                    valve.DOMAIN: {
                        "name": "test",
                        "state_topic": "state-topic",
                        "command_topic": "command-topic",
                        "reports_position": True,
                    }
                }
            },
            '{"state": "opening"}',
            "Missing required `position` attribute in json payload",
        ),
    ],
)
async def test_invalid_state_updates(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    message: str,
    err_message: str,
) -> None:
    """Test the controlling state via topic through position.

    Test  a `opening` or `closing` state update is reset correctly after sequential updates.
    """
    await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", message)
    state = hass.states.get("valve.test")
    assert err_message in caplog.text


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "reports_position": True,
                    "position_closed": -128,
                    "position_open": 127,
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("message", "asserted_state", "valve_position"),
    [
        ("-128", ValveState.CLOSED, 0),
        ("0", ValveState.OPEN, 50),
        ("127", ValveState.OPEN, 100),
        ("-130", ValveState.CLOSED, 0),
        ("130", ValveState.OPEN, 100),
        ('{"position": -128, "state": "opening"}', ValveState.OPENING, 0),
        ('{"position": -30, "state": "opening"}', ValveState.OPENING, 38),
        ('{"position": 30, "state": "open"}', ValveState.OPEN, 61),
        ('{"position": 127, "state": "closing"}', ValveState.CLOSING, 100),
        ('{"position": 100, "state": "closing"}', ValveState.CLOSING, 89),
        ('{"position": -128, "state": "closed"}', ValveState.CLOSED, 0),
        ('{"position": -130, "state": "closed"}', ValveState.CLOSED, 0),
        ('{"position": 130, "state": "open"}', ValveState.OPEN, 100),
    ],
)
async def test_state_via_state_trough_position_with_alt_range(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    message: str,
    asserted_state: str,
    valve_position: int | None,
) -> None:
    """Test the controlling state via topic through position and an alternative range.

    Test is still possible to process a `opening` or `closing` state update.
    Additional we test json messages can be processed containing both position and state.
    Incoming rendered positions are clamped between 0..100.
    """
    await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", message)

    state = hass.states.get("valve.test")
    assert state.state == asserted_state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == valve_position


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_stop": "SToP",
                    "payload_open": "OPeN",
                    "payload_close": "CLOsE",
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("service", "asserted_message"),
    [
        (SERVICE_CLOSE_VALVE, "CLOsE"),
        (SERVICE_OPEN_VALVE, "OPeN"),
        (SERVICE_STOP_VALVE, "SToP"),
    ],
)
async def test_controlling_valve_by_state(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    service: str,
    asserted_message: str,
) -> None:
    """Test controlling a valve by state."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        valve.DOMAIN,
        service,
        {ATTR_ENTITY_ID: "valve.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", asserted_message, 0, False
    )

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("hass_config", "supported_features"),
    [
        (DEFAULT_CONFIG, ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE),
        (
            help_custom_config(
                valve.DOMAIN,
                DEFAULT_CONFIG,
                ({"payload_open": "OPEN", "payload_close": "CLOSE"},),
            ),
            ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE,
        ),
        (
            help_custom_config(
                valve.DOMAIN,
                DEFAULT_CONFIG,
                ({"payload_open": "OPEN", "payload_close": None},),
            ),
            ValveEntityFeature.OPEN,
        ),
        (
            help_custom_config(
                valve.DOMAIN,
                DEFAULT_CONFIG,
                ({"payload_open": None, "payload_close": "CLOSE"},),
            ),
            ValveEntityFeature.CLOSE,
        ),
        (
            help_custom_config(
                valve.DOMAIN, DEFAULT_CONFIG, ({"payload_stop": "STOP"},)
            ),
            ValveEntityFeature.OPEN
            | ValveEntityFeature.CLOSE
            | ValveEntityFeature.STOP,
        ),
        (
            help_custom_config(
                valve.DOMAIN,
                DEFAULT_CONFIG_REPORTS_POSITION,
                ({"payload_stop": "STOP"},),
            ),
            ValveEntityFeature.OPEN
            | ValveEntityFeature.CLOSE
            | ValveEntityFeature.STOP
            | ValveEntityFeature.SET_POSITION,
        ),
    ],
)
async def test_supported_features(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    supported_features: ValveEntityFeature,
) -> None:
    """Test the valve's supported features."""
    assert await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state is not None
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == supported_features


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            valve.DOMAIN, DEFAULT_CONFIG_REPORTS_POSITION, ({"payload_open": "OPEN"},)
        ),
        help_custom_config(
            valve.DOMAIN, DEFAULT_CONFIG_REPORTS_POSITION, ({"payload_close": "CLOSE"},)
        ),
        help_custom_config(
            valve.DOMAIN, DEFAULT_CONFIG_REPORTS_POSITION, ({"state_open": "open"},)
        ),
        help_custom_config(
            valve.DOMAIN, DEFAULT_CONFIG_REPORTS_POSITION, ({"state_closed": "closed"},)
        ),
    ],
)
async def test_open_close_payload_config_not_allowed(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test open or close payload configs fail if valve reports position."""
    assert await mqtt_mock_entry()

    assert hass.states.get("valve.test") is None

    assert (
        "Options `payload_open`, `payload_close`, `state_open` and "
        "`state_closed` are not allowed if the valve reports a position." in caplog.text
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_stop": "STOP",
                    "optimistic": True,
                }
            }
        },
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "payload_stop": "STOP",
                }
            }
        },
    ],
)
@pytest.mark.parametrize(
    ("service", "asserted_message", "asserted_state"),
    [
        (SERVICE_CLOSE_VALVE, "CLOSE", ValveState.CLOSED),
        (SERVICE_OPEN_VALVE, "OPEN", ValveState.OPEN),
    ],
)
async def test_controlling_valve_by_state_optimistic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    service: str,
    asserted_message: str,
    asserted_state: str,
) -> None:
    """Test controlling a valve by state explicit and implicit optimistic."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        valve.DOMAIN,
        service,
        {ATTR_ENTITY_ID: "valve.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", asserted_message, 0, False
    )

    state = hass.states.get("valve.test")
    assert state.state == asserted_state


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_stop": "-1",
                    "reports_position": True,
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("service", "asserted_message"),
    [
        (SERVICE_CLOSE_VALVE, "0"),
        (SERVICE_OPEN_VALVE, "100"),
        (SERVICE_STOP_VALVE, "-1"),
    ],
)
async def test_controlling_valve_by_position(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    service: str,
    asserted_message: str,
) -> None:
    """Test controlling a valve by position."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        valve.DOMAIN,
        service,
        {ATTR_ENTITY_ID: "valve.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", asserted_message, 0, False
    )

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_stop": "-1",
                    "reports_position": True,
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("position", "asserted_message"),
    [(0, "0"), (30, "30"), (100, "100")],
)
async def test_controlling_valve_by_set_valve_position(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    position: int,
    asserted_message: str,
) -> None:
    """Test controlling a valve by position."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        valve.DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {ATTR_ENTITY_ID: "valve.test", ATTR_POSITION: position},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", asserted_message, 0, False
    )

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_stop": "-1",
                    "reports_position": True,
                    "optimistic": True,
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("position", "asserted_message", "asserted_position", "asserted_state"),
    [
        (0, "0", 0, ValveState.CLOSED),
        (30, "30", 30, ValveState.OPEN),
        (100, "100", 100, ValveState.OPEN),
    ],
)
async def test_controlling_valve_optimistic_by_set_valve_position(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    position: int,
    asserted_message: str,
    asserted_position: int,
    asserted_state: str,
) -> None:
    """Test controlling a valve optimistic by position."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        valve.DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {ATTR_ENTITY_ID: "valve.test", ATTR_POSITION: position},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", asserted_message, 0, False
    )

    state = hass.states.get("valve.test")
    assert state.state == asserted_state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == asserted_position


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_stop": "-1",
                    "reports_position": True,
                    "position_closed": -128,
                    "position_open": 127,
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("position", "asserted_message"),
    [(0, "-128"), (30, "-52"), (80, "76"), (100, "127")],
)
async def test_controlling_valve_with_alt_range_by_set_valve_position(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    position: int,
    asserted_message: str,
) -> None:
    """Test controlling a valve with an alt range by position."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        valve.DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {ATTR_ENTITY_ID: "valve.test", ATTR_POSITION: position},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", asserted_message, 0, False
    )

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "reports_position": True,
                    "position_closed": -128,
                    "position_open": 127,
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("service", "asserted_message"),
    [
        (SERVICE_CLOSE_VALVE, "-128"),
        (SERVICE_OPEN_VALVE, "127"),
    ],
)
async def test_controlling_valve_with_alt_range_by_position(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    service: str,
    asserted_message: str,
) -> None:
    """Test controlling a valve with an alt range by position."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        valve.DOMAIN,
        service,
        {ATTR_ENTITY_ID: "valve.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", asserted_message, 0, False
    )

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_stop": "STOP",
                    "optimistic": True,
                    "reports_position": True,
                }
            }
        },
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "payload_stop": "STOP",
                    "reports_position": True,
                }
            }
        },
    ],
)
@pytest.mark.parametrize(
    ("service", "asserted_message", "asserted_state", "asserted_position"),
    [
        (SERVICE_CLOSE_VALVE, "0", ValveState.CLOSED, 0),
        (SERVICE_OPEN_VALVE, "100", ValveState.OPEN, 100),
    ],
)
async def test_controlling_valve_by_position_optimistic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    service: str,
    asserted_message: str,
    asserted_state: str,
    asserted_position: int,
) -> None:
    """Test controlling a valve by state explicit and implicit optimistic."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_CURRENT_POSITION) is None

    await hass.services.async_call(
        valve.DOMAIN,
        service,
        {ATTR_ENTITY_ID: "valve.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", asserted_message, 0, False
    )

    state = hass.states.get("valve.test")
    assert state.state == asserted_state
    assert state.attributes[ATTR_CURRENT_POSITION] == asserted_position


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_stop": "-1",
                    "reports_position": True,
                    "optimistic": True,
                    "position_closed": -128,
                    "position_open": 127,
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("position", "asserted_message", "asserted_position", "asserted_state"),
    [
        (0, "-128", 0, ValveState.CLOSED),
        (30, "-52", 30, ValveState.OPEN),
        (50, "0", 50, ValveState.OPEN),
        (100, "127", 100, ValveState.OPEN),
    ],
)
async def test_controlling_valve_optimistic_alt_range_by_set_valve_position(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    position: int,
    asserted_message: str,
    asserted_position: int,
    asserted_state: str,
) -> None:
    """Test controlling a valve optimistic and alt range by position."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("valve.test")
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        valve.DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {ATTR_ENTITY_ID: "valve.test", ATTR_POSITION: position},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", asserted_message, 0, False
    )

    state = hass.states.get("valve.test")
    assert state.state == asserted_state
    assert state.attributes.get(ATTR_CURRENT_POSITION) == asserted_position


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, valve.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, valve.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry, valve.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry, valve.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "device_class": "water",
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

    state = hass.states.get("valve.test")
    assert state.attributes.get("device_class") == "water"


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: {
                    "name": "test",
                    "device_class": "abc123",
                    "state_topic": "test-topic",
                }
            }
        }
    ],
)
async def test_invalid_device_class(
    mqtt_mock_entry: MqttMockHAClientGenerator, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the setting of an invalid device class."""
    assert await mqtt_mock_entry()
    assert "expected ValveDeviceClass" in caplog.text


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, valve.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry,
        valve.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_VALVE_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, valve.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry, caplog, valve.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass, mqtt_mock_entry, caplog, valve.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry, valve.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                valve.DOMAIN: [
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
    """Test unique_id option only creates one valve per id."""
    await help_test_unique_id(hass, mqtt_mock_entry, valve.DOMAIN)


async def test_discovery_removal_valve(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test removal of discovered valve."""
    data = '{ "name": "test", "command_topic": "test_topic" }'
    await help_test_discovery_removal(hass, mqtt_mock_entry, valve.DOMAIN, data)


async def test_discovery_update_valve(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered valve."""
    config1 = {"name": "Beer", "command_topic": "test_topic"}
    config2 = {"name": "Milk", "command_topic": "test_topic"}
    await help_test_discovery_update(
        hass, mqtt_mock_entry, valve.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_valve(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered valve."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic" }'
    with patch(
        "homeassistant.components.mqtt.valve.MqttValve.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock_entry, valve.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic#" }'
    data2 = '{ "name": "Milk", "command_topic": "test_topic" }'
    await help_test_discovery_broken(hass, mqtt_mock_entry, valve.DOMAIN, data1, data2)


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT valve device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, valve.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT valve device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, valve.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, valve.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, valve.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, valve.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, valve.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry,
        valve.DOMAIN,
        DEFAULT_CONFIG,
        SERVICE_OPEN_VALVE,
        command_payload="OPEN",
    )


@pytest.mark.parametrize(
    ("service", "topic", "parameters", "payload", "template"),
    [
        (
            SERVICE_OPEN_VALVE,
            "command_topic",
            None,
            "OPEN",
            None,
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
    domain = valve.DOMAIN
    config = DEFAULT_CONFIG

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
    hass: HomeAssistant, mqtt_client_mock: MqttMockPahoClient
) -> None:
    """Test reloading the MQTT platform."""
    domain = valve.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("state_topic", "open", None, None),
        ("state_topic", "closing", None, None),
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
        valve.DOMAIN,
        DEFAULT_CONFIG[mqtt.DOMAIN][valve.DOMAIN],
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
    platform = valve.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unloading the config entry."""
    domain = valve.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            valve.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "availability_topic": "availability-topic",
                    "json_attributes_topic": "json-attributes-topic",
                    "state_topic": "test-topic",
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


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            valve.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "state_topic": "test-topic",
                    "value_template": "{{ value_json.some_var * 1 }}",
                },
            ),
        )
    ],
)
async def test_value_template_fails(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the rendering of MQTT value template fails."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, "test-topic", '{"some_var": null }')
    assert (
        "TypeError: unsupported operand type(s) for *: 'NoneType' and 'int' rendering template"
        in caplog.text
    )
