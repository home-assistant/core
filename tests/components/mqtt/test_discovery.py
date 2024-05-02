"""The tests for the MQTT discovery."""

import asyncio
import copy
import json
from pathlib import Path
import re
from unittest.mock import AsyncMock, call, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.components.mqtt.abbreviations import (
    ABBREVIATIONS,
    DEVICE_ABBREVIATIONS,
)
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.const import (
    EVENT_STATE_CHANGED,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
from homeassistant.setup import async_setup_component

from .test_common import help_all_subscribe_calls, help_test_unload_config_entry

from tests.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_mqtt_message,
    mock_config_flow,
    mock_platform,
)
from tests.typing import (
    MqttMockHAClientGenerator,
    MqttMockPahoClient,
    WebSocketGenerator,
)


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_DISCOVERY: False}],
)
async def test_subscribing_config_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test setting up discovery."""
    mqtt_mock = await mqtt_mock_entry()
    entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]

    discovery_topic = "homeassistant"
    await async_start(hass, discovery_topic, entry)

    call_args1 = mqtt_mock.async_subscribe.mock_calls[0][1]
    assert call_args1[2] == 0
    call_args2 = mqtt_mock.async_subscribe.mock_calls[1][1]
    assert call_args2[2] == 0
    topics = [call_args1[0], call_args2[0]]
    assert discovery_topic + "/+/+/config" in topics
    assert discovery_topic + "/+/+/+/config" in topics


@pytest.mark.parametrize(
    ("topic", "log"),
    [
        ("homeassistant/binary_sensor/bla/not_config", False),
        ("homeassistant/binary_sensor/rörkrökare/config", True),
    ],
)
async def test_invalid_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    topic: str,
    log: bool,
) -> None:
    """Test sending to invalid topic."""
    await mqtt_mock_entry()
    with patch(
        "homeassistant.components.mqtt.discovery.async_dispatcher_send"
    ) as mock_dispatcher_send:
        mock_dispatcher_send = AsyncMock(return_value=None)

        async_fire_mqtt_message(hass, topic, "{}")
        await hass.async_block_till_done()
        assert not mock_dispatcher_send.called
        if log:
            assert (
                f"Received message on illegal discovery topic '{topic}'" in caplog.text
            )
        else:
            assert "Received message on illegal discovery topic'" not in caplog.text
        caplog.clear()


async def test_invalid_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sending in invalid JSON."""
    await mqtt_mock_entry()
    with patch(
        "homeassistant.components.mqtt.discovery.async_dispatcher_send"
    ) as mock_dispatcher_send:
        mock_dispatcher_send = AsyncMock(return_value=None)

        async_fire_mqtt_message(
            hass, "homeassistant/binary_sensor/bla/config", "not json"
        )
        await hass.async_block_till_done()
        assert "Unable to parse JSON" in caplog.text
        assert not mock_dispatcher_send.called


@pytest.mark.parametrize(
    "domain", ["tag", "device_automation", Platform.SENSOR, Platform.LIGHT]
)
@pytest.mark.no_fail_on_log_exception
async def test_discovery_schema_error(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    domain: Platform | str,
) -> None:
    """Test unexpected error JSON config."""
    with patch(
        f"homeassistant.components.mqtt.{domain}.DISCOVERY_SCHEMA",
        side_effect=AttributeError("Attribute abc not found"),
    ):
        await mqtt_mock_entry()
        async_fire_mqtt_message(
            hass,
            f"homeassistant/{domain}/bla/config",
            '{"name": "Beer", "some_topic": "bla"}',
        )
        await hass.async_block_till_done()
        assert "AttributeError: Attribute abc not found" in caplog.text


async def test_invalid_config(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sending in JSON that violates the platform schema."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/alarm_control_panel/bla/config",
        '{"name": "abc", "state_topic": "home/alarm", '
        '"command_topic": "home/alarm/set", '
        '"qos": "some_invalid_value"}',
    )
    await hass.async_block_till_done()
    assert "Error 'expected int for dictionary value @ data['qos']'" in caplog.text


async def test_only_valid_components(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for a valid component."""
    await mqtt_mock_entry()
    with patch(
        "homeassistant.components.mqtt.discovery.async_dispatcher_send"
    ) as mock_dispatcher_send:
        invalid_component = "timer"

        mock_dispatcher_send = AsyncMock(return_value=None)

        async_fire_mqtt_message(
            hass, f"homeassistant/{invalid_component}/bla/config", "{}"
        )

    await hass.async_block_till_done()

    assert f"Integration {invalid_component} is not supported" in caplog.text

    assert not mock_dispatcher_send.called


async def test_correct_config_discovery(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test sending in correct JSON."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.beer")

    assert state is not None
    assert state.name == "Beer"
    assert ("binary_sensor", "bla") in hass.data["mqtt"].discovery_already_discovered


async def test_discovery_integration_info(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test logging discovery of new and updated items."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic", "o": {"name": "bla2mqtt", "sw": "1.0" } }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.beer")

    assert state is not None
    assert state.name == "Beer"

    assert (
        "Found new component: binary_sensor bla from external application bla2mqtt, version: 1.0"
        in caplog.text
    )
    caplog.clear()

    # Send an update and add support url
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Milk", "state_topic": "test-topic", "o": {"name": "bla2mqtt", "sw": "1.1", "url": "https://bla2mqtt.example.com/support" } }',
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.beer")

    assert state is not None
    assert state.name == "Milk"

    assert (
        "Component has already been discovered: binary_sensor bla, sending update from external application bla2mqtt, version: 1.1, support URL: https://bla2mqtt.example.com/support"
        in caplog.text
    )


@pytest.mark.parametrize(
    "config_message",
    [
        '{ "name": "Beer", "state_topic": "test-topic", "o": "bla2mqtt" }',
        '{ "name": "Beer", "state_topic": "test-topic", "o": 2.0 }',
        '{ "name": "Beer", "state_topic": "test-topic", "o": null }',
        '{ "name": "Beer", "state_topic": "test-topic", "o": {"sw": "bla2mqtt"} }',
    ],
)
async def test_discovery_with_invalid_integration_info(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    config_message: str,
) -> None:
    """Test sending in correct JSON."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        config_message,
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.beer")

    assert state is None
    assert (
        "Unable to parse origin information from discovery message, got" in caplog.text
    )


async def test_discover_fan(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test discovering an MQTT fan."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/fan/bla/config",
        '{ "name": "Beer", "command_topic": "test_topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.beer")

    assert state is not None
    assert state.name == "Beer"
    assert ("fan", "bla") in hass.data["mqtt"].discovery_already_discovered


async def test_discover_climate(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test discovering an MQTT climate component."""
    await mqtt_mock_entry()
    data = (
        '{ "name": "ClimateTest",'
        '  "current_temperature_topic": "climate/bla/current_temp",'
        '  "temperature_command_topic": "climate/bla/target_temp" }'
    )

    async_fire_mqtt_message(hass, "homeassistant/climate/bla/config", data)
    await hass.async_block_till_done()

    state = hass.states.get("climate.ClimateTest")

    assert state is not None
    assert state.name == "ClimateTest"
    assert ("climate", "bla") in hass.data["mqtt"].discovery_already_discovered


async def test_discover_alarm_control_panel(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test discovering an MQTT alarm control panel component."""
    await mqtt_mock_entry()
    data = (
        '{ "name": "AlarmControlPanelTest",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass, "homeassistant/alarm_control_panel/bla/config", data)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.AlarmControlPanelTest")

    assert state is not None
    assert state.name == "AlarmControlPanelTest"
    assert ("alarm_control_panel", "bla") in hass.data[
        "mqtt"
    ].discovery_already_discovered


@pytest.mark.parametrize(
    ("topic", "config", "entity_id", "name", "domain"),
    [
        (
            "homeassistant/alarm_control_panel/object/bla/config",
            '{ "name": "Hello World 1", "obj_id": "hello_id", "state_topic": "test-topic", "command_topic": "test-topic" }',
            "alarm_control_panel.hello_id",
            "Hello World 1",
            "alarm_control_panel",
        ),
        (
            "homeassistant/binary_sensor/object/bla/config",
            '{ "name": "Hello World 2", "obj_id": "hello_id", "state_topic": "test-topic" }',
            "binary_sensor.hello_id",
            "Hello World 2",
            "binary_sensor",
        ),
        (
            "homeassistant/button/object/bla/config",
            '{ "name": "Hello World button", "obj_id": "hello_id", "command_topic": "test-topic" }',
            "button.hello_id",
            "Hello World button",
            "button",
        ),
        (
            "homeassistant/camera/object/bla/config",
            '{ "name": "Hello World 3", "obj_id": "hello_id", "state_topic": "test-topic", "topic": "test-topic" }',
            "camera.hello_id",
            "Hello World 3",
            "camera",
        ),
        (
            "homeassistant/climate/object/bla/config",
            '{ "name": "Hello World 4", "obj_id": "hello_id", "state_topic": "test-topic" }',
            "climate.hello_id",
            "Hello World 4",
            "climate",
        ),
        (
            "homeassistant/cover/object/bla/config",
            '{ "name": "Hello World 5", "obj_id": "hello_id", "state_topic": "test-topic" }',
            "cover.hello_id",
            "Hello World 5",
            "cover",
        ),
        (
            "homeassistant/fan/object/bla/config",
            '{ "name": "Hello World 6", "obj_id": "hello_id", "state_topic": "test-topic", "command_topic": "test-topic" }',
            "fan.hello_id",
            "Hello World 6",
            "fan",
        ),
        (
            "homeassistant/humidifier/object/bla/config",
            '{ "name": "Hello World 7", "obj_id": "hello_id", "state_topic": "test-topic", "target_humidity_command_topic": "test-topic", "command_topic": "test-topic" }',
            "humidifier.hello_id",
            "Hello World 7",
            "humidifier",
        ),
        (
            "homeassistant/number/object/bla/config",
            '{ "name": "Hello World 8", "obj_id": "hello_id", "state_topic": "test-topic", "command_topic": "test-topic" }',
            "number.hello_id",
            "Hello World 8",
            "number",
        ),
        (
            "homeassistant/scene/object/bla/config",
            '{ "name": "Hello World 9", "obj_id": "hello_id", "state_topic": "test-topic", "command_topic": "test-topic" }',
            "scene.hello_id",
            "Hello World 9",
            "scene",
        ),
        (
            "homeassistant/select/object/bla/config",
            '{ "name": "Hello World 10", "obj_id": "hello_id", "state_topic": "test-topic", "options": [ "opt1", "opt2" ], "command_topic": "test-topic" }',
            "select.hello_id",
            "Hello World 10",
            "select",
        ),
        (
            "homeassistant/sensor/object/bla/config",
            '{ "name": "Hello World 11", "obj_id": "hello_id", "state_topic": "test-topic" }',
            "sensor.hello_id",
            "Hello World 11",
            "sensor",
        ),
        (
            "homeassistant/switch/object/bla/config",
            '{ "name": "Hello World 12", "obj_id": "hello_id", "state_topic": "test-topic", "command_topic": "test-topic" }',
            "switch.hello_id",
            "Hello World 12",
            "switch",
        ),
        (
            "homeassistant/light/object/bla/config",
            '{ "name": "Hello World 13", "obj_id": "hello_id", "state_topic": "test-topic", "command_topic": "test-topic" }',
            "light.hello_id",
            "Hello World 13",
            "light",
        ),
        (
            "homeassistant/light/object/bla/config",
            '{ "name": "Hello World 14", "obj_id": "hello_id", "state_topic": "test-topic", "command_topic": "test-topic", "schema": "json" }',
            "light.hello_id",
            "Hello World 14",
            "light",
        ),
        (
            "homeassistant/light/object/bla/config",
            '{ "name": "Hello World 15", "obj_id": "hello_id", "state_topic": "test-topic", "command_off_template": "template", "command_on_template": "template", "command_topic": "test-topic", "schema": "template" }',
            "light.hello_id",
            "Hello World 15",
            "light",
        ),
        (
            "homeassistant/vacuum/object/bla/config",
            '{ "name": "Hello World 16", "obj_id": "hello_id", "state_topic": "test-topic", "schema": "state" }',
            "vacuum.hello_id",
            "Hello World 16",
            "vacuum",
        ),
        (
            "homeassistant/valve/object/bla/config",
            '{ "name": "Hello World 17", "obj_id": "hello_id", "state_topic": "test-topic" }',
            "valve.hello_id",
            "Hello World 17",
            "valve",
        ),
        (
            "homeassistant/lock/object/bla/config",
            '{ "name": "Hello World 18", "obj_id": "hello_id", "state_topic": "test-topic", "command_topic": "test-topic" }',
            "lock.hello_id",
            "Hello World 18",
            "lock",
        ),
        (
            "homeassistant/device_tracker/object/bla/config",
            '{ "name": "Hello World 19", "obj_id": "hello_id", "state_topic": "test-topic" }',
            "device_tracker.hello_id",
            "Hello World 19",
            "device_tracker",
        ),
    ],
)
async def test_discovery_with_object_id(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    topic: str,
    config: str,
    entity_id: str,
    name: str,
    domain: str,
) -> None:
    """Test discovering an MQTT entity with object_id."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, topic, config)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state is not None
    assert state.name == name
    assert (domain, "object bla") in hass.data["mqtt"].discovery_already_discovered


async def test_discovery_incl_nodeid(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test sending in correct JSON with optional node_id included."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/my_node_id/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.beer")

    assert state is not None
    assert state.name == "Beer"
    assert ("binary_sensor", "my_node_id bla") in hass.data[
        "mqtt"
    ].discovery_already_discovered


async def test_non_duplicate_discovery(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for a non duplicate component."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.beer")
    state_duplicate = hass.states.get("binary_sensor.beer1")

    assert state is not None
    assert state.name == "Beer"
    assert state_duplicate is None
    assert "Component has already been discovered: binary_sensor bla" in caplog.text


async def test_removal(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test removal of component through empty discovery message."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.beer")
    assert state is not None

    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla/config", "")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.beer")
    assert state is None


async def test_rediscover(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test rediscover of removed component."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.beer")
    assert state is not None

    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla/config", "")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.beer")
    assert state is None

    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.beer")
    assert state is not None


async def test_rapid_rediscover(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test immediate rediscover of removed component."""
    await mqtt_mock_entry()
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.beer")
    assert state is not None
    assert len(events) == 1

    # Removal immediately followed by rediscover
    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla/config", "")
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla/config", "")
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Milk", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("binary_sensor")) == 1
    state = hass.states.get("binary_sensor.milk")
    assert state is not None

    assert len(events) == 5
    # Remove the entity
    assert events[1].data["entity_id"] == "binary_sensor.beer"
    assert events[1].data["new_state"] is None
    # Add the entity
    assert events[2].data["entity_id"] == "binary_sensor.beer"
    assert events[2].data["old_state"] is None
    # Remove the entity
    assert events[3].data["entity_id"] == "binary_sensor.beer"
    assert events[3].data["new_state"] is None
    # Add the entity
    assert events[4].data["entity_id"] == "binary_sensor.milk"
    assert events[4].data["old_state"] is None


async def test_rapid_rediscover_unique(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test immediate rediscover of removed component."""
    await mqtt_mock_entry()
    events = []

    @callback
    def test_callback(event: Event) -> None:
        """Verify event got called."""
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, test_callback)

    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla2/config",
        '{ "name": "Ale", "state_topic": "test-topic", "unique_id": "very_unique" }',
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.ale")
    assert state is not None
    assert len(events) == 1

    # Duplicate unique_id, immediately followed by correct unique_id
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic", "unique_id": "very_unique" }',
    )
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic", "unique_id": "even_uniquer" }',
    )
    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla/config", "")
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Milk", "state_topic": "test-topic", "unique_id": "even_uniquer" }',
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("binary_sensor")) == 2
    state = hass.states.get("binary_sensor.ale")
    assert state is not None
    state = hass.states.get("binary_sensor.milk")
    assert state is not None

    assert len(events) == 4
    # Add the entity
    assert events[1].data["entity_id"] == "binary_sensor.beer"
    assert events[1].data["old_state"] is None
    # Remove the entity
    assert events[2].data["entity_id"] == "binary_sensor.beer"
    assert events[2].data["new_state"] is None
    # Add the entity
    assert events[3].data["entity_id"] == "binary_sensor.milk"
    assert events[3].data["old_state"] is None


async def test_rapid_reconfigure(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test immediate reconfigure of added component."""
    await mqtt_mock_entry()
    events = []

    @callback
    def test_callback(event: Event) -> None:
        """Verify event got called."""
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, test_callback)

    # Discovery immediately followed by reconfig
    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla/config", "")
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic1" }',
    )
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Milk", "state_topic": "test-topic2" }',
    )
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Wine", "state_topic": "test-topic3" }',
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("binary_sensor")) == 1
    state = hass.states.get("binary_sensor.beer")
    assert state is not None

    assert len(events) == 3
    # Add the entity
    assert events[0].data["entity_id"] == "binary_sensor.beer"
    assert events[0].data["old_state"] is None
    assert events[0].data["new_state"].attributes["friendly_name"] == "Beer"
    # Update the entity
    assert events[1].data["entity_id"] == "binary_sensor.beer"
    assert events[1].data["new_state"] is not None
    assert events[1].data["old_state"] is not None
    assert events[1].data["new_state"].attributes["friendly_name"] == "Milk"
    # Update the entity
    assert events[2].data["entity_id"] == "binary_sensor.beer"
    assert events[2].data["new_state"] is not None
    assert events[2].data["old_state"] is not None
    assert events[2].data["new_state"].attributes["friendly_name"] == "Wine"


async def test_duplicate_removal(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for a non duplicate component."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/binary_sensor/bla/config",
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla/config", "")
    await hass.async_block_till_done()
    assert "Component has already been discovered: binary_sensor bla" in caplog.text
    caplog.clear()
    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla/config", "")
    await hass.async_block_till_done()

    assert "Component has already been discovered: binary_sensor bla" not in caplog.text


async def test_cleanup_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test discvered device is cleaned up when entry removed from device."""
    mqtt_mock = await mqtt_mock_entry()
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    data = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )

    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is not None
    entity_entry = entity_registry.async_get("sensor.none_mqtt_sensor")
    assert entity_entry is not None

    state = hass.states.get("sensor.none_mqtt_sensor")
    assert state is not None

    # Remove MQTT from the device
    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    response = await ws_client.remove_device(
        device_entry.id, mqtt_config_entry.entry_id
    )
    assert response["success"]
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify device and registry entries are cleared
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is None
    entity_entry = entity_registry.async_get("sensor.none_mqtt_sensor")
    assert entity_entry is None

    # Verify state is removed
    state = hass.states.get("sensor.none_mqtt_sensor")
    assert state is None
    await hass.async_block_till_done()

    # Verify retained discovery topic has been cleared
    mqtt_mock.async_publish.assert_called_once_with(
        "homeassistant/sensor/bla/config", "", 0, True
    )


async def test_cleanup_device_mqtt(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test discvered device is cleaned up when removed through MQTT."""
    mqtt_mock = await mqtt_mock_entry()
    data = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )

    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is not None
    entity_entry = entity_registry.async_get("sensor.none_mqtt_sensor")
    assert entity_entry is not None

    state = hass.states.get("sensor.none_mqtt_sensor")
    assert state is not None

    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", "")
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify device and registry entries are cleared
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is None
    entity_entry = entity_registry.async_get("sensor.none_mqtt_sensor")
    assert entity_entry is None

    # Verify state is removed
    state = hass.states.get("sensor.none_mqtt_sensor")
    assert state is None
    await hass.async_block_till_done()

    # Verify retained discovery topics have not been cleared again
    mqtt_mock.async_publish.assert_not_called()


async def test_cleanup_device_multiple_config_entries(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test discovered device is cleaned up when entry removed from device."""
    assert await async_setup_component(hass, "config", {})
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry()
    ws_client = await hass_ws_client(hass)

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={("mac", "12:34:56:AB:CD:EF")},
    )
    assert device_entry is not None

    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]

    sensor_config = {
        "device": {"connections": [["mac", "12:34:56:AB:CD:EF"]]},
        "state_topic": "foobar/sensor",
        "unique_id": "unique",
    }
    tag_config = {
        "device": {"connections": [["mac", "12:34:56:AB:CD:EF"]]},
        "topic": "test-topic",
    }
    trigger_config = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"connections": [["mac", "12:34:56:AB:CD:EF"]]},
    }

    sensor_data = json.dumps(sensor_config)
    tag_data = json.dumps(tag_config)
    trigger_data = json.dumps(trigger_config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", sensor_data)
    async_fire_mqtt_message(hass, "homeassistant/tag/bla/config", tag_data)
    async_fire_mqtt_message(
        hass, "homeassistant/device_automation/bla/config", trigger_data
    )
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_registry.async_get_device(
        connections={("mac", "12:34:56:AB:CD:EF")}
    )
    assert device_entry is not None
    assert device_entry.config_entries == {
        mqtt_config_entry.entry_id,
        config_entry.entry_id,
    }
    entity_entry = entity_registry.async_get("sensor.none_mqtt_sensor")
    assert entity_entry is not None

    state = hass.states.get("sensor.none_mqtt_sensor")
    assert state is not None

    # Remove MQTT from the device
    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    response = await ws_client.remove_device(
        device_entry.id, mqtt_config_entry.entry_id
    )
    assert response["success"]

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify device is still there but entity is cleared
    device_entry = device_registry.async_get_device(
        connections={("mac", "12:34:56:AB:CD:EF")}
    )
    assert device_entry is not None
    entity_entry = entity_registry.async_get("sensor.none_mqtt_sensor")
    assert device_entry.config_entries == {config_entry.entry_id}
    assert entity_entry is None

    # Verify state is removed
    state = hass.states.get("sensor.none_mqtt_sensor")
    assert state is None
    await hass.async_block_till_done()

    # Verify retained discovery topic has been cleared
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("homeassistant/sensor/bla/config", "", 0, True),
            call("homeassistant/tag/bla/config", "", 0, True),
            call("homeassistant/device_automation/bla/config", "", 0, True),
        ],
        any_order=True,
    )


async def test_cleanup_device_multiple_config_entries_mqtt(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test discovered device is cleaned up when removed through MQTT."""
    mqtt_mock = await mqtt_mock_entry()
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={("mac", "12:34:56:AB:CD:EF")},
    )

    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]

    sensor_config = {
        "device": {"connections": [["mac", "12:34:56:AB:CD:EF"]]},
        "state_topic": "foobar/sensor",
        "unique_id": "unique",
    }
    tag_config = {
        "device": {"connections": [["mac", "12:34:56:AB:CD:EF"]]},
        "topic": "test-topic",
    }
    trigger_config = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"connections": [["mac", "12:34:56:AB:CD:EF"]]},
    }

    sensor_data = json.dumps(sensor_config)
    tag_data = json.dumps(tag_config)
    trigger_data = json.dumps(trigger_config)
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", sensor_data)
    async_fire_mqtt_message(hass, "homeassistant/tag/bla/config", tag_data)
    async_fire_mqtt_message(
        hass, "homeassistant/device_automation/bla/config", trigger_data
    )
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_registry.async_get_device(
        connections={("mac", "12:34:56:AB:CD:EF")}
    )
    assert device_entry is not None
    assert device_entry.config_entries == {
        mqtt_config_entry.entry_id,
        config_entry.entry_id,
    }
    entity_entry = entity_registry.async_get("sensor.none_mqtt_sensor")
    assert entity_entry is not None

    state = hass.states.get("sensor.none_mqtt_sensor")
    assert state is not None

    # Send MQTT messages to remove
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", "")
    async_fire_mqtt_message(hass, "homeassistant/tag/bla/config", "")
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", "")

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify device is still there but entity is cleared
    device_entry = device_registry.async_get_device(
        connections={("mac", "12:34:56:AB:CD:EF")}
    )
    assert device_entry is not None
    entity_entry = entity_registry.async_get("sensor.none_mqtt_sensor")
    assert device_entry.config_entries == {config_entry.entry_id}
    assert entity_entry is None

    # Verify state is removed
    state = hass.states.get("sensor.none_mqtt_sensor")
    assert state is None
    await hass.async_block_till_done()

    # Verify retained discovery topics have not been cleared again
    mqtt_mock.async_publish.assert_not_called()


async def test_discovery_expansion(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test expansion of abbreviated discovery payload."""
    await mqtt_mock_entry()
    data = (
        '{ "~": "some/base/topic",'
        '  "name": "DiscoveryExpansionTest1",'
        '  "stat_t": "test_topic/~",'
        '  "cmd_t": "~/test_topic",'
        '  "availability": ['
        "    {"
        '      "topic":"~/avail_item1",'
        '      "payload_available": "available",'
        '      "payload_not_available": "not_available"'
        "    },"
        "    {"
        '      "t":"avail_item2/~",'
        '      "pl_avail": "available",'
        '      "pl_not_avail": "not_available"'
        "    }"
        "  ],"
        '  "dev":{'
        '    "ids":["5706DF"],'
        '    "name":"DiscoveryExpansionTest1 Device",'
        '    "mdl":"Generic",'
        '    "hw":"rev1",'
        '    "sw":"1.2.3.4",'
        '    "mf":"None",'
        '    "sa":"default_area"'
        "  }"
        "}"
    )

    async_fire_mqtt_message(hass, "homeassistant/switch/bla/config", data)
    await hass.async_block_till_done()

    state = hass.states.get("switch.DiscoveryExpansionTest1")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "avail_item2/some/base/topic", "available")
    await hass.async_block_till_done()

    state = hass.states.get("switch.DiscoveryExpansionTest1")
    assert state is not None
    assert state.name == "DiscoveryExpansionTest1"
    assert ("switch", "bla") in hass.data["mqtt"].discovery_already_discovered
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "test_topic/some/base/topic", "ON")

    state = hass.states.get("switch.DiscoveryExpansionTest1")
    assert state and state.state == STATE_ON

    async_fire_mqtt_message(hass, "some/base/topic/avail_item1", "not_available")
    await hass.async_block_till_done()

    state = hass.states.get("switch.DiscoveryExpansionTest1")
    assert state and state.state == STATE_UNAVAILABLE


async def test_discovery_expansion_2(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test expansion of abbreviated discovery payload."""
    await mqtt_mock_entry()
    data = (
        '{ "~": "some/base/topic",'
        '  "name": "DiscoveryExpansionTest1",'
        '  "stat_t": "test_topic/~",'
        '  "cmd_t": "~/test_topic",'
        '  "availability": {'
        '    "t":"~/avail_item1",'
        '    "pl_avail": "available",'
        '    "pl_not_avail": "not_available"'
        "  },"
        '  "dev":{'
        '    "ids":["5706DF"],'
        '    "name":"DiscoveryExpansionTest1 Device",'
        '    "mdl":"Generic",'
        '    "hw":"rev1",'
        '    "sw":"1.2.3.4",'
        '    "mf":"None",'
        '    "sa":"default_area"'
        "  }"
        "}"
    )

    async_fire_mqtt_message(hass, "homeassistant/switch/bla/config", data)
    await hass.async_block_till_done()

    state = hass.states.get("switch.DiscoveryExpansionTest1")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "some/base/topic/avail_item1", "available")
    await hass.async_block_till_done()

    state = hass.states.get("switch.DiscoveryExpansionTest1")
    assert state is not None
    assert state.name == "DiscoveryExpansionTest1"
    assert ("switch", "bla") in hass.data["mqtt"].discovery_already_discovered
    assert state.state == STATE_UNKNOWN


async def test_discovery_expansion_3(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test expansion of broken discovery payload."""
    await mqtt_mock_entry()
    data = (
        '{ "~": "some/base/topic",'
        '  "name": "DiscoveryExpansionTest1",'
        '  "stat_t": "test_topic/~",'
        '  "cmd_t": "~/test_topic",'
        '  "availability": "incorrect",'
        '  "dev":{'
        '    "ids":["5706DF"],'
        '    "name":"DiscoveryExpansionTest1 Device",'
        '    "mdl":"Generic",'
        '    "hw":"rev1",'
        '    "sw":"1.2.3.4",'
        '    "mf":"None",'
        '    "sa":"default_area"'
        "  }"
        "}"
    )

    async_fire_mqtt_message(hass, "homeassistant/switch/bla/config", data)
    await hass.async_block_till_done()
    assert hass.states.get("switch.DiscoveryExpansionTest1") is None
    # Make sure the malformed availability data does not trip up discovery by asserting
    # there are schema valdiation errors in the log
    assert "expected a dictionary @ data['availability'][0]" in caplog.text


async def test_discovery_expansion_without_encoding_and_value_template_1(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test expansion of raw availability payload with a template as list."""
    await mqtt_mock_entry()
    data = (
        '{ "~": "some/base/topic",'
        '  "name": "DiscoveryExpansionTest1",'
        '  "stat_t": "test_topic/~",'
        '  "cmd_t": "~/test_topic",'
        '  "encoding":"",'
        '  "availability": [{'
        '    "topic":"~/avail_item1",'
        '    "payload_available": "1",'
        '    "payload_not_available": "0",'
        '    "value_template":"{{value|unpack(\'b\')}}"'
        "  }],"
        '  "dev":{'
        '    "ids":["5706DF"],'
        '    "name":"DiscoveryExpansionTest1 Device",'
        '    "mdl":"Generic",'
        '    "hw":"rev1",'
        '    "sw":"1.2.3.4",'
        '    "mf":"None",'
        '    "sa":"default_area"'
        "  }"
        "}"
    )

    async_fire_mqtt_message(hass, "homeassistant/switch/bla/config", data)
    await hass.async_block_till_done()

    state = hass.states.get("switch.DiscoveryExpansionTest1")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "some/base/topic/avail_item1", b"\x01")
    await hass.async_block_till_done()

    state = hass.states.get("switch.DiscoveryExpansionTest1")
    assert state is not None
    assert state.name == "DiscoveryExpansionTest1"
    assert ("switch", "bla") in hass.data["mqtt"].discovery_already_discovered
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "some/base/topic/avail_item1", b"\x00")

    state = hass.states.get("switch.DiscoveryExpansionTest1")
    assert state and state.state == STATE_UNAVAILABLE


async def test_discovery_expansion_without_encoding_and_value_template_2(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test expansion of raw availability payload with a template directly."""
    await mqtt_mock_entry()
    data = (
        '{ "~": "some/base/topic",'
        '  "name": "DiscoveryExpansionTest1",'
        '  "stat_t": "test_topic/~",'
        '  "cmd_t": "~/test_topic",'
        '  "availability_topic":"~/avail_item1",'
        '  "payload_available": "1",'
        '  "payload_not_available": "0",'
        '  "encoding":"",'
        '  "availability_template":"{{ value | unpack(\'b\') }}",'
        '  "dev":{'
        '    "ids":["5706DF"],'
        '    "name":"DiscoveryExpansionTest1 Device",'
        '    "mdl":"Generic",'
        '    "hw":"rev1",'
        '    "sw":"1.2.3.4",'
        '    "mf":"None",'
        '    "sa":"default_area"'
        "  }"
        "}"
    )

    async_fire_mqtt_message(hass, "homeassistant/switch/bla/config", data)
    await hass.async_block_till_done()

    state = hass.states.get("switch.DiscoveryExpansionTest1")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "some/base/topic/avail_item1", b"\x01")
    await hass.async_block_till_done()

    state = hass.states.get("switch.DiscoveryExpansionTest1")
    assert state is not None
    assert state.name == "DiscoveryExpansionTest1"
    assert ("switch", "bla") in hass.data["mqtt"].discovery_already_discovered
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "some/base/topic/avail_item1", b"\x00")

    state = hass.states.get("switch.DiscoveryExpansionTest1")
    assert state and state.state == STATE_UNAVAILABLE


ABBREVIATIONS_WHITE_LIST = [
    # MQTT client/server/trigger settings
    # Integration info
    "CONF_SUPPORT_URL",
    # Undocumented device configuration
    "CONF_DEPRECATED_VIA_HUB",
    "CONF_VIA_DEVICE",
    # Already short
    "CONF_FAN_MODE_LIST",
    "CONF_HOLD_LIST",
    "CONF_HS",
    "CONF_MODE_LIST",
    "CONF_PRECISION",
    "CONF_QOS",
    "CONF_SCHEMA",
    "CONF_SWING_MODE_LIST",
    "CONF_TEMP_STEP",
    # Removed
    "CONF_WHITE_VALUE",
]

EXCLUDED_MODULES = {
    "const.py",
    "config.py",
    "config_flow.py",
    "device_trigger.py",
    "trigger.py",
}


async def test_missing_discover_abbreviations(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Check MQTT platforms for missing abbreviations."""
    await mqtt_mock_entry()
    missing = []
    regex = re.compile(r"(CONF_[a-zA-Z\d_]*) *= *[\'\"]([a-zA-Z\d_]*)[\'\"]")
    for fil in Path(mqtt.__file__).parent.rglob("*.py"):
        if fil.name in EXCLUDED_MODULES:
            continue
        with open(fil, encoding="utf-8") as file:
            matches = re.findall(regex, file.read())
            missing.extend(
                f"{fil}: no abbreviation for {match[1]} ({match[0]})"
                for match in matches
                if match[1] not in ABBREVIATIONS.values()
                and match[1] not in DEVICE_ABBREVIATIONS.values()
                and match[0] not in ABBREVIATIONS_WHITE_LIST
            )

    assert not missing


async def test_no_implicit_state_topic_switch(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test no implicit state topic for switch."""
    await mqtt_mock_entry()
    data = '{ "name": "Test1", "command_topic": "cmnd" }'

    async_fire_mqtt_message(hass, "homeassistant/switch/bla/config", data)
    await hass.async_block_till_done()

    state = hass.states.get("switch.Test1")
    assert state is not None
    assert state.name == "Test1"
    assert ("switch", "bla") in hass.data["mqtt"].discovery_already_discovered
    assert state.state == STATE_UNKNOWN
    assert state.attributes["assumed_state"] is True

    async_fire_mqtt_message(hass, "homeassistant/switch/bla/state", "ON")

    state = hass.states.get("switch.Test1")
    assert state and state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [
        {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_DISCOVERY_PREFIX: "my_home/homeassistant/register",
        }
    ],
)
async def test_complex_discovery_topic_prefix(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Tests handling of discovery topic prefix with multiple slashes."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(
        hass,
        ("my_home/homeassistant/register/binary_sensor/node1/object1/config"),
        '{ "name": "Beer", "state_topic": "test-topic" }',
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.beer")

    assert state is not None
    assert state.name == "Beer"
    assert ("binary_sensor", "node1 object1") in hass.data[
        "mqtt"
    ].discovery_already_discovered


@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.UNSUBSCRIBE_COOLDOWN", 0.0)
async def test_mqtt_integration_discovery_subscribe_unsubscribe(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Check MQTT integration discovery subscribe and unsubscribe."""
    mqtt_mock = await mqtt_mock_entry()
    mock_platform(hass, "comp.config_flow", None)

    entry = hass.config_entries.async_entries("mqtt")[0]
    mqtt_mock().connected = True

    with patch(
        "homeassistant.components.mqtt.discovery.async_get_mqtt",
        return_value={"comp": ["comp/discovery/#"]},
    ):
        await async_start(hass, "homeassistant", entry)
        await hass.async_block_till_done()
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    assert ("comp/discovery/#", 0) in help_all_subscribe_calls(mqtt_client_mock)
    assert not mqtt_client_mock.unsubscribe.called

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> FlowResult:
            """Test mqtt step."""
            return self.async_abort(reason="already_configured")

    assert not mqtt_client_mock.unsubscribe.called

    wait_unsub = asyncio.Event()

    def _mock_unsubscribe(topics: list[str]) -> tuple[int, int]:
        wait_unsub.set()
        return (0, 0)

    with (
        mock_config_flow("comp", TestFlow),
        patch.object(mqtt_client_mock, "unsubscribe", side_effect=_mock_unsubscribe),
    ):
        async_fire_mqtt_message(hass, "comp/discovery/bla/config", "")
        await wait_unsub.wait()
        mqtt_client_mock.unsubscribe.assert_called_once_with(["comp/discovery/#"])


@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.UNSUBSCRIBE_COOLDOWN", 0.0)
async def test_mqtt_discovery_unsubscribe_once(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Check MQTT integration discovery unsubscribe once."""
    mqtt_mock = await mqtt_mock_entry()
    mock_platform(hass, "comp.config_flow", None)

    entry = hass.config_entries.async_entries("mqtt")[0]
    mqtt_mock().connected = True

    with patch(
        "homeassistant.components.mqtt.discovery.async_get_mqtt",
        return_value={"comp": ["comp/discovery/#"]},
    ):
        await async_start(hass, "homeassistant", entry)
        await hass.async_block_till_done()
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    assert ("comp/discovery/#", 0) in help_all_subscribe_calls(mqtt_client_mock)
    assert not mqtt_client_mock.unsubscribe.called

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> FlowResult:
            """Test mqtt step."""
            await asyncio.sleep(0.1)
            return self.async_abort(reason="already_configured")

    with mock_config_flow("comp", TestFlow):
        async_fire_mqtt_message(hass, "comp/discovery/bla/config", "")
        async_fire_mqtt_message(hass, "comp/discovery/bla/config", "")
        await asyncio.sleep(0.1)
        await hass.async_block_till_done()
        await hass.async_block_till_done()
        mqtt_client_mock.unsubscribe.assert_called_once_with(["comp/discovery/#"])


async def test_clear_config_topic_disabled_entity(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the discovery topic is removed when a disabled entity is removed."""
    mqtt_mock = await mqtt_mock_entry()
    # discover an entity that is not enabled by default
    config = {
        "state_topic": "homeassistant_test/sensor/sbfspot_0/sbfspot_12345/",
        "unique_id": "sbfspot_12345",
        "enabled_by_default": False,
        "device": {
            "identifiers": ["sbfspot_12345"],
            "name": "abc123",
            "sw_version": "1.0",
            "connections": [["mac", "12:34:56:AB:CD:EF"]],
        },
    }
    async_fire_mqtt_message(
        hass,
        "homeassistant/sensor/sbfspot_0/sbfspot_12345/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    # discover an entity that is not unique (part 1), will be added
    config_not_unique1 = copy.deepcopy(config)
    config_not_unique1["name"] = "sbfspot_12345_1"
    config_not_unique1["unique_id"] = "not_unique"
    config_not_unique1.pop("enabled_by_default")
    async_fire_mqtt_message(
        hass,
        "homeassistant/sensor/sbfspot_0/sbfspot_12345_1/config",
        json.dumps(config_not_unique1),
    )
    # discover an entity that is not unique (part 2), will not be added
    config_not_unique2 = copy.deepcopy(config_not_unique1)
    config_not_unique2["name"] = "sbfspot_12345_2"
    async_fire_mqtt_message(
        hass,
        "homeassistant/sensor/sbfspot_0/sbfspot_12345_2/config",
        json.dumps(config_not_unique2),
    )
    await hass.async_block_till_done()
    assert "Platform mqtt does not generate unique IDs" in caplog.text

    assert hass.states.get("sensor.abc123_sbfspot_12345") is None  # disabled
    assert hass.states.get("sensor.abc123_sbfspot_12345_1") is not None  # enabled
    assert hass.states.get("sensor.abc123_sbfspot_12345_2") is None  # not unique

    # Verify device is created
    device_entry = device_registry.async_get_device(
        connections={("mac", "12:34:56:AB:CD:EF")}
    )
    assert device_entry is not None

    # Remove the device from the registry
    device_registry.async_remove_device(device_entry.id)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Assert all valid discovery topics are cleared
    assert mqtt_mock.async_publish.call_count == 2
    assert (
        call("homeassistant/sensor/sbfspot_0/sbfspot_12345/config", "", 0, True)
        in mqtt_mock.async_publish.mock_calls
    )
    assert (
        call("homeassistant/sensor/sbfspot_0/sbfspot_12345_1/config", "", 0, True)
        in mqtt_mock.async_publish.mock_calls
    )


async def test_clean_up_registry_monitoring(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    tmp_path: Path,
) -> None:
    """Test registry monitoring hook is removed after a reload."""
    await mqtt_mock_entry()
    hooks: dict = hass.data["mqtt"].discovery_registry_hooks
    # discover an entity that is not enabled by default
    config1 = {
        "name": "sbfspot_12345",
        "state_topic": "homeassistant_test/sensor/sbfspot_0/sbfspot_12345/",
        "unique_id": "sbfspot_12345",
        "enabled_by_default": False,
        "device": {
            "identifiers": ["sbfspot_12345"],
            "name": "sbfspot_12345",
            "sw_version": "1.0",
            "connections": [["mac", "12:34:56:AB:CD:EF"]],
        },
    }
    # Publish it config
    # Since it is not enabled_by_default the sensor will not be loaded
    # it should register a hook for monitoring the entiry registry
    async_fire_mqtt_message(
        hass,
        "homeassistant/sensor/sbfspot_0/sbfspot_12345/config",
        json.dumps(config1),
    )
    await hass.async_block_till_done()
    assert len(hooks) == 1

    # Publish it again no new monitor should be started
    async_fire_mqtt_message(
        hass,
        "homeassistant/sensor/sbfspot_0/sbfspot_12345/config",
        json.dumps(config1),
    )
    await hass.async_block_till_done()
    assert len(hooks) == 1

    # Verify device is created
    device_entry = device_registry.async_get_device(
        connections={("mac", "12:34:56:AB:CD:EF")}
    )
    assert device_entry is not None

    # Enload the entry
    # The monitoring should be cleared
    await help_test_unload_config_entry(hass)
    assert len(hooks) == 0


async def test_unique_id_collission_has_priority(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the unique_id collision detection has priority over registry disabled items."""
    await mqtt_mock_entry()
    config = {
        "state_topic": "homeassistant_test/sensor/sbfspot_0/sbfspot_12345/",
        "unique_id": "sbfspot_12345",
        "enabled_by_default": False,
        "device": {
            "identifiers": ["sbfspot_12345"],
            "name": "abc123",
            "sw_version": "1.0",
            "connections": [["mac", "12:34:56:AB:CD:EF"]],
        },
    }
    # discover an entity that is not unique and disabled by default (part 1), will be added
    config_not_unique1 = copy.deepcopy(config)
    config_not_unique1["name"] = "sbfspot_12345_1"
    config_not_unique1["unique_id"] = "not_unique"
    async_fire_mqtt_message(
        hass,
        "homeassistant/sensor/sbfspot_0/sbfspot_12345_1/config",
        json.dumps(config_not_unique1),
    )
    # discover an entity that is not unique (part 2), will not be added, and the registry entry is cleared
    config_not_unique2 = copy.deepcopy(config_not_unique1)
    config_not_unique2["name"] = "sbfspot_12345_2"
    async_fire_mqtt_message(
        hass,
        "homeassistant/sensor/sbfspot_0/sbfspot_12345_2/config",
        json.dumps(config_not_unique2),
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.abc123_sbfspot_12345_1") is None  # not enabled
    assert hass.states.get("sensor.abc123_sbfspot_12345_2") is None  # not unique

    # Verify the first entity is created
    assert entity_registry.async_get("sensor.abc123_sbfspot_12345_1") is not None
    # Verify the second entity is not created because it is not unique
    assert entity_registry.async_get("sensor.abc123_sbfspot_12345_2") is None


async def test_update_with_bad_config_not_breaks_discovery(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test a bad update does not break discovery."""
    await mqtt_mock_entry()
    # discover a sensor
    config1 = {
        "name": "sbfspot_12345",
        "state_topic": "homeassistant_test/sensor/sbfspot_0/state",
    }
    async_fire_mqtt_message(
        hass,
        "homeassistant/sensor/sbfspot_0/config",
        json.dumps(config1),
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.sbfspot_12345") is not None
    # update with a breaking config
    config2 = {
        "name": "sbfspot_12345",
        "availability": 1,
        "state_topic": "homeassistant_test/sensor/sbfspot_0/state",
    }
    async_fire_mqtt_message(
        hass,
        "homeassistant/sensor/sbfspot_0/config",
        json.dumps(config2),
    )
    await hass.async_block_till_done()
    # update the state topic
    config3 = {
        "name": "sbfspot_12345",
        "state_topic": "homeassistant_test/sensor/sbfspot_0/new_state_topic",
    }
    async_fire_mqtt_message(
        hass,
        "homeassistant/sensor/sbfspot_0/config",
        json.dumps(config3),
    )
    await hass.async_block_till_done()

    # Send an update for the state
    async_fire_mqtt_message(
        hass,
        "homeassistant_test/sensor/sbfspot_0/new_state_topic",
        "new_value",
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.sbfspot_12345")
    assert state and state.state == "new_value"
