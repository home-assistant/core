"""The tests for the MQTT discovery."""

import asyncio
import copy
import json
import logging
from pathlib import Path
import re
from typing import Any
from unittest.mock import ANY, AsyncMock, call, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.mqtt.abbreviations import (
    ABBREVIATIONS,
    DEVICE_ABBREVIATIONS,
)
from homeassistant.components.mqtt.const import SUPPORTED_COMPONENTS
from homeassistant.components.mqtt.discovery import (
    MQTT_DISCOVERY_DONE,
    MQTT_DISCOVERY_NEW,
    MQTT_DISCOVERY_UPDATED,
    MQTTDiscoveryPayload,
    async_start,
)
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_STATE_CHANGED,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
from homeassistant.setup import async_setup_component
from homeassistant.util.signal_type import SignalTypeFormat

from .conftest import ENTRY_DEFAULT_BIRTH_MESSAGE
from .test_common import help_all_subscribe_calls, help_test_unload_config_entry
from .test_tag import DEFAULT_TAG_ID, DEFAULT_TAG_SCAN

from tests.common import (
    MockConfigEntry,
    MockModule,
    async_capture_events,
    async_fire_mqtt_message,
    async_get_device_automations,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
from tests.typing import (
    MqttMockHAClientGenerator,
    MqttMockPahoClient,
    WebSocketGenerator,
)

TEST_SINGLE_CONFIGS = [
    (
        "homeassistant/device_automation/0AFFD2/bla1/config",
        {
            "device": {"identifiers": ["0AFFD2"], "name": "test_device"},
            "o": {"name": "Foo2Mqtt", "sw": "1.40.2", "url": "https://www.foo2mqtt.io"},
            "automation_type": "trigger",
            "payload": "short_press",
            "topic": "foobar/triggers/button1",
            "type": "button_short_press",
            "subtype": "button_1",
        },
    ),
    (
        "homeassistant/sensor/0AFFD2/bla2/config",
        {
            "device": {"identifiers": ["0AFFD2"], "name": "test_device"},
            "o": {"name": "Foo2Mqtt", "sw": "1.40.2", "url": "https://www.foo2mqtt.io"},
            "state_topic": "foobar/sensors/bla2/state",
            "unique_id": "bla002",
        },
    ),
    (
        "homeassistant/tag/0AFFD2/bla3/config",
        {
            "device": {"identifiers": ["0AFFD2"], "name": "test_device"},
            "o": {"name": "Foo2Mqtt", "sw": "1.40.2", "url": "https://www.foo2mqtt.io"},
            "topic": "foobar/tags/bla3/see",
        },
    ),
]
TEST_DEVICE_CONFIG = {
    "device": {"identifiers": ["0AFFD2"], "name": "test_device"},
    "o": {"name": "Foo2Mqtt", "sw": "1.50.0", "url": "https://www.foo2mqtt.io"},
    "cmps": {
        "bla1": {
            "platform": "device_automation",
            "automation_type": "trigger",
            "payload": "short_press",
            "topic": "foobar/triggers/button1",
            "type": "button_short_press",
            "subtype": "button_1",
        },
        "bla2": {
            "platform": "sensor",
            "state_topic": "foobar/sensors/bla2/state",
            "unique_id": "bla002",
            "name": "mqtt_sensor",
        },
        "bla3": {
            "platform": "tag",
            "topic": "foobar/tags/bla3/see",
        },
    },
}
TEST_DEVICE_DISCOVERY_TOPIC = "homeassistant/device/0AFFD2/config"


async def help_check_discovered_items(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, tag_mock: AsyncMock
) -> None:
    """Help checking discovered test items are still available."""

    # Check the device_trigger was discovered
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is not None
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 1
    # Check the sensor was discovered
    state = hass.states.get("sensor.test_device_mqtt_sensor")
    assert state is not None

    # Check the tag works
    async_fire_mqtt_message(hass, "foobar/tags/bla3/see", DEFAULT_TAG_SCAN)
    await hass.async_block_till_done()
    tag_mock.assert_called_once_with(ANY, DEFAULT_TAG_ID, device_entry.id)
    tag_mock.reset_mock()


@pytest.fixture
def mqtt_data_flow_calls() -> list[MqttServiceInfo]:
    """Return list to capture MQTT data data flow calls."""
    return []


@pytest.fixture
async def mock_mqtt_flow(
    hass: HomeAssistant, mqtt_data_flow_calls: list[MqttServiceInfo]
) -> config_entries.ConfigFlow:
    """Test fixure for mqtt integration flow.

    The topic is used as a unique ID.
    The component test domain used is: `comp`.

    Creates an entry if does not exist.
    Updates an entry if it exists, and there is an updated payload.
    """

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> FlowResult:
            """Test mqtt step."""
            await asyncio.sleep(0)
            mqtt_data_flow_calls.append(discovery_info)
            # Abort a flow if there is an update for the existing entry
            if entry := self.hass.config_entries.async_entry_for_domain_unique_id(
                "comp", discovery_info.topic
            ):
                hass.config_entries.async_update_entry(
                    entry,
                    data={
                        "name": discovery_info.topic,
                        "payload": discovery_info.payload,
                    },
                )
                raise AbortFlow("already_configured")
            await self.async_set_unique_id(discovery_info.topic)
            return self.async_create_entry(
                title="Test",
                data={"name": discovery_info.topic, "payload": discovery_info.payload},
            )

    return TestFlow


@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [{mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_DISCOVERY: False}],
)
async def test_subscribing_config_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting up discovery."""
    mqtt_mock = await mqtt_mock_entry()
    entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]

    discovery_topic = "homeassistant"
    await async_start(hass, discovery_topic, entry)

    topics = [call[1][0] for call in mqtt_mock.async_subscribe.mock_calls]
    for component in SUPPORTED_COMPONENTS:
        assert f"{discovery_topic}/{component}/+/config" in topics
        assert f"{discovery_topic}/{component}/+/+/config" in topics


@pytest.mark.parametrize(
    ("topic", "log"),
    [
        ("homeassistant/binary_sensor/bla/not_config", False),
        ("homeassistant/binary_sensor/rörkrökare/config", True),
        ("homeassistant/device/bla/not_config", False),
        ("homeassistant/device/rörkrökare/config", True),
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


@pytest.mark.parametrize(
    "discovery_topic",
    ["homeassistant/binary_sensor/bla/config", "homeassistant/device/bla/config"],
)
async def test_invalid_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    discovery_topic: str,
) -> None:
    """Test sending in invalid JSON."""
    await mqtt_mock_entry()
    with patch(
        "homeassistant.components.mqtt.discovery.async_dispatcher_send"
    ) as mock_dispatcher_send:
        mock_dispatcher_send = AsyncMock(return_value=None)

        async_fire_mqtt_message(hass, discovery_topic, "not json")
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


async def test_invalid_device_discovery_config(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sending in JSON that violates the discovery schema if device or platform key is missing."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        "homeassistant/device/bla/config",
        '{ "o": {"name": "foobar"}, "cmps": '
        '{ "acp1": {"name": "abc", "state_topic": "home/alarm", '
        '"unique_id": "very_unique",'
        '"command_topic": "home/alarm/set", '
        '"platform":"alarm_control_panel"}}}',
    )
    await hass.async_block_till_done()
    assert (
        "Invalid MQTT device discovery payload for bla, "
        "required key not provided @ data['device']" in caplog.text
    )

    caplog.clear()
    async_fire_mqtt_message(
        hass,
        "homeassistant/device/bla/config",
        '{ "o": {"name": "foobar"}, "dev": {"identifiers": ["ABDE03"]}, '
        '"cmps": { "acp1": {"name": "abc", "state_topic": "home/alarm", '
        '"command_topic": "home/alarm/set" }}}',
    )
    await hass.async_block_till_done()
    assert (
        "Invalid MQTT device discovery payload for bla, "
        "required key not provided @ data['components']['acp1']['platform']"
        in caplog.text
    )

    caplog.clear()
    async_fire_mqtt_message(
        hass,
        "homeassistant/device/bla/config",
        '{ "o": {"name": "foobar"}, "dev": {"identifiers": ["ABDE03"]}, "cmps": ""}',
    )
    await hass.async_block_till_done()
    assert (
        "Invalid MQTT device discovery payload for bla, "
        "expected a dictionary for dictionary value @ data['components']" in caplog.text
    )


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

    assert not mock_dispatcher_send.called


async def test_correct_config_discovery(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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


@pytest.mark.parametrize(
    ("discovery_topic", "payloads", "discovery_id"),
    [
        (
            "homeassistant/binary_sensor/bla/config",
            (
                '{"name":"Beer","state_topic": "test-topic",'
                '"unique_id": "very_unique1",'
                '"o":{"name":"bla2mqtt","sw":"1.0"},'
                '"dev":{"identifiers":["bla"],"name": "bla"}}',
                '{"name":"Milk","state_topic": "test-topic",'
                '"unique_id": "very_unique1",'
                '"o":{"name":"bla2mqtt","sw":"1.1",'
                '"url":"https://bla2mqtt.example.com/support"},'
                '"dev":{"identifiers":["bla"],"name": "bla"}}',
            ),
            "bla",
        ),
        (
            "homeassistant/device/bla/config",
            (
                '{"cmps":{"bin_sens1":{"platform":"binary_sensor",'
                '"unique_id": "very_unique1",'
                '"name":"Beer","state_topic": "test-topic"}},'
                '"o":{"name":"bla2mqtt","sw":"1.0"},'
                '"dev":{"identifiers":["bla"],"name": "bla"}}',
                '{"cmps":{"bin_sens1":{"platform":"binary_sensor",'
                '"unique_id": "very_unique1",'
                '"name":"Milk","state_topic": "test-topic"}},'
                '"o":{"name":"bla2mqtt","sw":"1.1",'
                '"url":"https://bla2mqtt.example.com/support"},'
                '"dev":{"identifiers":["bla"],"name": "bla"}}',
            ),
            "bla bin_sens1",
        ),
    ],
)
async def test_discovery_integration_info(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    discovery_topic: str,
    payloads: tuple[str, str],
    discovery_id: str,
) -> None:
    """Test discovery of integration info."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        discovery_topic,
        payloads[0],
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.bla_beer")

    assert state is not None
    assert state.name == "bla Beer"

    assert (
        "Processing device discovery for 'bla' from external "
        "application bla2mqtt, version: 1.0"
        in caplog.text
        or f"Found new component: binary_sensor {discovery_id} from external application bla2mqtt, version: 1.0"
        in caplog.text
    )
    caplog.clear()

    # Send an update and add support url
    async_fire_mqtt_message(
        hass,
        discovery_topic,
        payloads[1],
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.bla_beer")

    assert state is not None
    assert state.name == "bla Milk"

    assert (
        f"Component has already been discovered: binary_sensor {discovery_id}"
        in caplog.text
    )


@pytest.mark.parametrize(
    ("single_configs", "device_discovery_topic", "device_config"),
    [(TEST_SINGLE_CONFIGS, TEST_DEVICE_DISCOVERY_TOPIC, TEST_DEVICE_CONFIG)],
)
async def test_discovery_migration_to_device_base(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    tag_mock: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    single_configs: list[tuple[str, dict[str, Any]]],
    device_discovery_topic: str,
    device_config: dict[str, Any],
) -> None:
    """Test the migration of single discovery to device discovery."""
    await mqtt_mock_entry()

    # Discovery single config schema
    for discovery_topic, config in single_configs:
        payload = json.dumps(config)
        async_fire_mqtt_message(
            hass,
            discovery_topic,
            payload,
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    await help_check_discovered_items(hass, device_registry, tag_mock)

    # Try to migrate to device based discovery without migrate_discovery flag
    payload = json.dumps(device_config)
    async_fire_mqtt_message(
        hass,
        device_discovery_topic,
        payload,
    )
    await hass.async_block_till_done()
    assert (
        "Received a conflicting MQTT discovery message for device_automation "
        "'0AFFD2 bla1' which was previously discovered on topic homeassistant/"
        "device_automation/0AFFD2/bla1/config from external application Foo2Mqtt, "
        "version: 1.40.2; the conflicting discovery message was received on topic "
        "homeassistant/device/0AFFD2/config from external application Foo2Mqtt, "
        "version: 1.50.0; for support visit https://www.foo2mqtt.io" in caplog.text
    )
    assert (
        "Received a conflicting MQTT discovery message for entity sensor."
        "test_device_mqtt_sensor; the entity was previously discovered on topic "
        "homeassistant/sensor/0AFFD2/bla2/config from external application Foo2Mqtt, "
        "version: 1.40.2; the conflicting discovery message was received on topic "
        "homeassistant/device/0AFFD2/config from external application Foo2Mqtt, "
        "version: 1.50.0; for support visit https://www.foo2mqtt.io" in caplog.text
    )
    assert (
        "Received a conflicting MQTT discovery message for tag '0AFFD2 bla3' which "
        "was previously discovered on topic homeassistant/tag/0AFFD2/bla3/config "
        "from external application Foo2Mqtt, version: 1.40.2; the conflicting "
        "discovery message was received on topic homeassistant/device/0AFFD2/config "
        "from external application Foo2Mqtt, version: 1.50.0; for support visit "
        "https://www.foo2mqtt.io" in caplog.text
    )

    # Check we still have our mqtt items
    await help_check_discovered_items(hass, device_registry, tag_mock)

    # Test Enable discovery migration
    # Discovery single config schema
    caplog.clear()
    for discovery_topic, _ in single_configs:
        # migr_discvry is abbreviation for migrate_discovery
        payload = json.dumps({"migr_discvry": True})
        async_fire_mqtt_message(
            hass,
            discovery_topic,
            payload,
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Assert we still have our device entry
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is not None
    # Check our trigger was unloaden
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 0
    # Check the sensor was unloaded
    state = hass.states.get("sensor.test_device_mqtt_sensor")
    assert state is None
    # Check the entity registry entry is retained
    assert entity_registry.async_is_registered("sensor.test_device_mqtt_sensor")

    assert (
        "Migration to MQTT device discovery schema started for device_automation "
        "'0AFFD2 bla1' from external application Foo2Mqtt, version: 1.40.2 on topic "
        "homeassistant/device_automation/0AFFD2/bla1/config. To complete migration, "
        "publish a device discovery message with device_automation '0AFFD2 bla1'. "
        "After completed migration, publish an empty (retained) payload to "
        "homeassistant/device_automation/0AFFD2/bla1/config" in caplog.text
    )
    assert (
        "Migration to MQTT device discovery schema started for entity sensor."
        "test_device_mqtt_sensor from external application Foo2Mqtt, version: 1.40.2 "
        "on topic homeassistant/sensor/0AFFD2/bla2/config. To complete migration, "
        "publish a device discovery message with sensor entity '0AFFD2 bla2'. After "
        "completed migration, publish an empty (retained) payload to "
        "homeassistant/sensor/0AFFD2/bla2/config" in caplog.text
    )

    # Migrate to device based discovery
    caplog.clear()
    payload = json.dumps(device_config)
    async_fire_mqtt_message(
        hass,
        device_discovery_topic,
        payload,
    )
    await hass.async_block_till_done()

    caplog.clear()
    for _ in range(2):
        # Test publishing an empty payload twice to the migrated discovery topics
        # does not remove the migrated items
        for discovery_topic, _ in single_configs:
            async_fire_mqtt_message(
                hass,
                discovery_topic,
                "",
            )
        await hass.async_block_till_done()
        await hass.async_block_till_done()

        # Check we still have our mqtt items after publishing an
        # empty payload to the old discovery topics
        await help_check_discovered_items(hass, device_registry, tag_mock)

    # Check we cannot accidentally migrate back and remove the items
    caplog.clear()
    for discovery_topic, config in single_configs:
        payload = json.dumps(config)
        async_fire_mqtt_message(
            hass,
            discovery_topic,
            payload,
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert (
        "Received a conflicting MQTT discovery message for device_automation "
        "'0AFFD2 bla1' which was previously discovered on topic homeassistant/device"
        "/0AFFD2/config from external application Foo2Mqtt, version: 1.50.0; the "
        "conflicting discovery message was received on topic homeassistant/"
        "device_automation/0AFFD2/bla1/config from external application Foo2Mqtt, "
        "version: 1.40.2; for support visit https://www.foo2mqtt.io" in caplog.text
    )
    assert (
        "Received a conflicting MQTT discovery message for entity sensor."
        "test_device_mqtt_sensor; the entity was previously discovered on topic "
        "homeassistant/device/0AFFD2/config from external application Foo2Mqtt, "
        "version: 1.50.0; the conflicting discovery message was received on topic "
        "homeassistant/sensor/0AFFD2/bla2/config from external application Foo2Mqtt, "
        "version: 1.40.2; for support visit https://www.foo2mqtt.io" in caplog.text
    )
    assert (
        "Received a conflicting MQTT discovery message for tag '0AFFD2 bla3' which was "
        "previously discovered on topic homeassistant/device/0AFFD2/config from "
        "external application Foo2Mqtt, version: 1.50.0; the conflicting discovery "
        "message was received on topic homeassistant/tag/0AFFD2/bla3/config from "
        "external application Foo2Mqtt, version: 1.40.2; for support visit "
        "https://www.foo2mqtt.io" in caplog.text
    )

    caplog.clear()
    for discovery_topic, config in single_configs:
        payload = json.dumps(config)
        async_fire_mqtt_message(
            hass,
            discovery_topic,
            "",
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Check we still have our mqtt items after publishing an
    # empty payload to the old discovery topics
    await help_check_discovered_items(hass, device_registry, tag_mock)

    # Check we can remove the config using the new discovery topic
    async_fire_mqtt_message(
        hass,
        device_discovery_topic,
        "",
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    # Check the device was removed as all device components were removed
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is None
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(
    "config",
    [
        {"state_topic": "foobar/sensors/bla2/state", "name": "none_test"},
        {
            "state_topic": "foobar/sensors/bla2/state",
            "name": "none_test",
            "unique_id": "very_unique",
        },
        {
            "state_topic": "foobar/sensors/bla2/state",
            "device": {"identifiers": ["0AFFD2"], "name": "none_test"},
        },
    ],
)
async def test_discovery_migration_unique_id(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    config: dict[str, Any],
) -> None:
    """Test entity has a unique_id and device context when migrating."""
    await mqtt_mock_entry()

    discovery_topic = "homeassistant/sensor/0AFFD2/bla2/config"

    # Discovery with single config schema
    payload = json.dumps(config)
    async_fire_mqtt_message(
        hass,
        discovery_topic,
        payload,
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Try discovery migration
    payload = json.dumps({"migr_discvry": True})
    async_fire_mqtt_message(
        hass,
        discovery_topic,
        payload,
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Assert the migration attempt fails
    assert "Discovery migration is not possible" in caplog.text


@pytest.mark.parametrize(
    ("single_configs", "device_discovery_topic", "device_config"),
    [(TEST_SINGLE_CONFIGS, TEST_DEVICE_DISCOVERY_TOPIC, TEST_DEVICE_CONFIG)],
)
async def test_discovery_rollback_to_single_base(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    tag_mock: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    single_configs: list[tuple[str, dict[str, Any]]],
    device_discovery_topic: str,
    device_config: dict[str, Any],
) -> None:
    """Test the rollback of device discovery to a single component discovery."""
    await mqtt_mock_entry()

    # Start device based discovery
    # any single component discovery will be migrated
    payload = json.dumps(device_config)
    async_fire_mqtt_message(
        hass,
        device_discovery_topic,
        payload,
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    await help_check_discovered_items(hass, device_registry, tag_mock)

    # Migrate to single component discovery
    # Test the schema
    caplog.clear()
    payload = json.dumps({"migrate_discovery": "invalid"})
    async_fire_mqtt_message(
        hass,
        device_discovery_topic,
        payload,
    )
    await hass.async_block_till_done()
    assert "Invalid MQTT device discovery payload for 0AFFD2" in caplog.text

    # Set the correct migrate_discovery flag in the device payload
    # to allow rollback
    payload = json.dumps({"migrate_discovery": True})
    async_fire_mqtt_message(
        hass,
        device_discovery_topic,
        payload,
    )
    await hass.async_block_till_done()

    # Check the log messages
    assert (
        "Rollback to MQTT platform discovery schema started for entity sensor."
        "test_device_mqtt_sensor from external application Foo2Mqtt, version: 1.50.0 "
        "on topic homeassistant/device/0AFFD2/config. To complete rollback, publish a "
        "platform discovery message with sensor entity '0AFFD2 bla2'. After completed "
        "rollback, publish an empty (retained) payload to "
        "homeassistant/device/0AFFD2/config" in caplog.text
    )
    assert (
        "Rollback to MQTT platform discovery schema started for device_automation "
        "'0AFFD2 bla1' from external application Foo2Mqtt, version: 1.50.0 on topic "
        "homeassistant/device/0AFFD2/config. To complete rollback, publish a platform "
        "discovery message with device_automation '0AFFD2 bla1'. After completed "
        "rollback, publish an empty (retained) payload to "
        "homeassistant/device/0AFFD2/config" in caplog.text
    )

    # Assert we still have our device entry
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is not None
    # Check our trigger was unloaded
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 0
    # Check the sensor was unloaded
    state = hass.states.get("sensor.test_device_mqtt_sensor")
    assert state is None
    # Check the entity registry entry is retained
    assert entity_registry.async_is_registered("sensor.test_device_mqtt_sensor")

    # Publish the new component based payloads
    # to switch back to component based discovery
    for discovery_topic, config in single_configs:
        payload = json.dumps(config)
        async_fire_mqtt_message(
            hass,
            discovery_topic,
            payload,
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Check we still have our mqtt items
    # await help_check_discovered_items(hass, device_registry, tag_mock)

    for _ in range(2):
        # Test publishing an empty payload twice to the migrated discovery topic
        # does not remove the migrated items
        async_fire_mqtt_message(
            hass,
            device_discovery_topic,
            "",
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()

        # Check we still have our mqtt items after publishing an
        # empty payload to the old discovery topics
        await help_check_discovered_items(hass, device_registry, tag_mock)

    # Check we cannot accidentally migrate back and remove the items
    payload = json.dumps(device_config)
    async_fire_mqtt_message(
        hass,
        device_discovery_topic,
        payload,
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Check we still have our mqtt items after publishing an
    # empty payload to the old discovery topics
    await help_check_discovered_items(hass, device_registry, tag_mock)

    # Check we can remove the the config using the new discovery topics
    for discovery_topic, config in single_configs:
        payload = json.dumps(config)
        async_fire_mqtt_message(
            hass,
            discovery_topic,
            "",
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    # Check the device was removed as all device components were removed
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is None


@pytest.mark.parametrize(
    ("discovery_topic", "payload"),
    [
        (
            "homeassistant/binary_sensor/bla/config",
            '{"state_topic": "test-topic",'
            '"name":"bla","unique_id":"very_unique1",'
            '"avty": {"topic": "avty-topic"},'
            '"o":{"name":"bla2mqtt","sw":"1.0"},'
            '"dev":{"identifiers":["bla"],"name":"Beer"}}',
        ),
        (
            "homeassistant/device/bla/config",
            '{"cmps":{"bin_sens1":{"platform":"binary_sensor",'
            '"name":"bla","unique_id":"very_unique1",'
            '"state_topic": "test-topic"}},'
            '"avty": {"topic": "avty-topic"},'
            '"o":{"name":"bla2mqtt","sw":"1.0"},'
            '"dev":{"identifiers":["bla"],"name":"Beer"}}',
        ),
    ],
    ids=["component", "device"],
)
async def test_discovery_availability(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    discovery_topic: str,
    payload: str,
) -> None:
    """Test device discovery with shared availability mapping."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        discovery_topic,
        payload,
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.beer_bla")
    assert state is not None
    assert state.name == "Beer bla"
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(
        hass,
        "avty-topic",
        "online",
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.beer_bla")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(
        hass,
        "test-topic",
        "ON",
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.beer_bla")
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("discovery_topic", "payload"),
    [
        (
            "homeassistant/device/bla/config",
            '{"cmps":{"bin_sens1":{"platform":"binary_sensor",'
            '"unique_id":"very_unique",'
            '"avty": {"topic": "avty-topic-component"},'
            '"name":"Beer","state_topic": "test-topic"}},'
            '"avty": {"topic": "avty-topic-device"},'
            '"o":{"name":"bla2mqtt","sw":"1.0"},"dev":{"identifiers":["bla"]}}',
        ),
        (
            "homeassistant/device/bla/config",
            '{"cmps":{"bin_sens1":{"platform":"binary_sensor",'
            '"unique_id":"very_unique",'
            '"availability_topic": "avty-topic-component",'
            '"name":"Beer","state_topic": "test-topic"}},'
            '"availability_topic": "avty-topic-device",'
            '"o":{"name":"bla2mqtt","sw":"1.0"},"dev":{"identifiers":["bla"]}}',
        ),
    ],
    ids=["test1", "test2"],
)
async def test_discovery_component_availability_overridden(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    discovery_topic: str,
    payload: str,
) -> None:
    """Test device discovery with overridden shared availability mapping."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass,
        discovery_topic,
        payload,
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.none_beer")
    assert state is not None
    assert state.name == "Beer"
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(
        hass,
        "avty-topic-device",
        "online",
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.none_beer")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(
        hass,
        "avty-topic-component",
        "online",
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.none_beer")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(
        hass,
        "test-topic",
        "ON",
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.none_beer")
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("discovery_topic", "config_message", "error_message"),
    [
        (
            "homeassistant/binary_sensor/bla/config",
            '{ "name": "Beer", "unique_id": "very_unique", '
            '"state_topic": "test-topic", "o": "bla2mqtt" }',
            "Unable to parse origin information from discovery message",
        ),
        (
            "homeassistant/binary_sensor/bla/config",
            '{ "name": "Beer", "unique_id": "very_unique", '
            '"state_topic": "test-topic", "o": 2.0 }',
            "Unable to parse origin information from discovery message",
        ),
        (
            "homeassistant/binary_sensor/bla/config",
            '{ "name": "Beer", "unique_id": "very_unique", '
            '"state_topic": "test-topic", "o": null }',
            "Unable to parse origin information from discovery message",
        ),
        (
            "homeassistant/binary_sensor/bla/config",
            '{ "name": "Beer", "unique_id": "very_unique", '
            '"state_topic": "test-topic", "o": {"sw": "bla2mqtt"} }',
            "Unable to parse origin information from discovery message",
        ),
        (
            "homeassistant/device/bla/config",
            '{"dev":{"identifiers":["bs1"]},"cmps":{"bs1":'
            '{"platform":"binary_sensor","name":"Beer","unique_id": "very_unique",'
            '"state_topic":"test-topic"}},"o": "bla2mqtt"}',
            "Invalid MQTT device discovery payload for bla, "
            "expected a dictionary for dictionary value @ data['origin']",
        ),
        (
            "homeassistant/device/bla/config",
            '{"dev":{"identifiers":["bs1"]},"cmps":{"bs1":'
            '{"platform":"binary_sensor","name":"Beer","unique_id": "very_unique",'
            '"state_topic":"test-topic"}},"o": 2.0}',
            "Invalid MQTT device discovery payload for bla, "
            "expected a dictionary for dictionary value @ data['origin']",
        ),
        (
            "homeassistant/device/bla/config",
            '{"dev":{"identifiers":["bs1"]},"cmps":{"bs1":'
            '{"platform":"binary_sensor","name":"Beer","unique_id": "very_unique",'
            '"state_topic":"test-topic"}},"o": null}',
            "Invalid MQTT device discovery payload for bla, "
            "expected a dictionary for dictionary value @ data['origin']",
        ),
        (
            "homeassistant/device/bla/config",
            '{"dev":{"identifiers":["bs1"]},"cmps":{"bs1":'
            '{"platform":"binary_sensor","name":"Beer","unique_id": "very_unique",'
            '"state_topic":"test-topic"}},"o": {"sw": "bla2mqtt"}}',
            "Invalid MQTT device discovery payload for bla, "
            "required key not provided @ data['origin']['name']",
        ),
    ],
)
async def test_discovery_with_invalid_integration_info(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    discovery_topic: str,
    config_message: str,
    error_message: str,
) -> None:
    """Test sending in correct JSON."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, discovery_topic, config_message)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.none_beer")

    assert state is None
    assert error_message in caplog.text


async def test_discover_fan(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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


@pytest.mark.parametrize(
    ("discovery_payloads", "entity_ids"),
    [
        (
            {
                "homeassistant/sensor/sens1/config": "{"
                '"device":{"identifiers":["0AFFD2"]},'
                '"state_topic": "foobar/sensor1",'
                '"unique_id": "unique1",'
                '"name": "sensor1"'
                "}",
                "homeassistant/sensor/sens2/config": "{"
                '"device":{"identifiers":["0AFFD2"]},'
                '"state_topic": "foobar/sensor2",'
                '"unique_id": "unique2",'
                '"name": "sensor2"'
                "}",
            },
            ["sensor.none_sensor1", "sensor.none_sensor2"],
        ),
        (
            {
                "homeassistant/device/bla/config": "{"
                '"device":{"identifiers":["0AFFD2"]},'
                '"o": {"name": "foobar"},'
                '"cmps": {"sens1": {'
                '"platform": "sensor",'
                '"name": "sensor1",'
                '"state_topic": "foobar/sensor1",'
                '"unique_id": "unique1"'
                '},"sens2": {'
                '"platform": "sensor",'
                '"name": "sensor2",'
                '"state_topic": "foobar/sensor2",'
                '"unique_id": "unique2"'
                "}}}"
            },
            ["sensor.none_sensor1", "sensor.none_sensor2"],
        ),
    ],
)
async def test_cleanup_device_manual(
    hass: HomeAssistant,
    mock_debouncer: asyncio.Event,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    discovery_payloads: dict[str, str],
    entity_ids: list[str],
) -> None:
    """Test discovered device is cleaned up when entry removed from device."""
    mqtt_mock = await mqtt_mock_entry()
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    mock_debouncer.clear()
    for discovery_topic, discovery_payload in discovery_payloads.items():
        async_fire_mqtt_message(hass, discovery_topic, discovery_payload)
    await mock_debouncer.wait()

    # Verify device and registry entries are created
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is not None

    for entity_id in entity_ids:
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None

        state = hass.states.get(entity_id)
        assert state is not None

    # Remove MQTT from the device
    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    mock_debouncer.clear()
    response = await ws_client.remove_device(
        device_entry.id, mqtt_config_entry.entry_id
    )
    assert response["success"]
    await mock_debouncer.wait()
    await hass.async_block_till_done()

    # Verify device and registry entries are cleared
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is None
    entity_entry = entity_registry.async_get("sensor.none_mqtt_sensor")
    assert entity_entry is None

    # Verify state is removed
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state is None

    # Verify retained discovery topics have been cleared
    mqtt_mock.async_publish.assert_has_calls(
        [call(discovery_topic, None, 0, True) for discovery_topic in discovery_payloads]
    )

    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(
    ("discovery_topic", "discovery_payload", "entity_ids"),
    [
        (
            "homeassistant/sensor/bla/config",
            '{ "device":{"identifiers":["0AFFD2"]},'
            '  "state_topic": "foobar/sensor",'
            '  "unique_id": "unique" }',
            ["sensor.none_mqtt_sensor"],
        ),
        (
            "homeassistant/device/bla/config",
            '{ "device":{"identifiers":["0AFFD2"]},'
            '  "o": {"name": "foobar"},'
            '  "cmps": {"sens1": {'
            '  "platform": "sensor",'
            '  "name": "sensor1",'
            '  "state_topic": "foobar/sensor1",'
            '  "unique_id": "unique1"'
            ' },"sens2": {'
            '  "platform": "sensor",'
            '  "name": "sensor2",'
            '  "state_topic": "foobar/sensor2",'
            '  "unique_id": "unique2"'
            "}}}",
            ["sensor.none_sensor1", "sensor.none_sensor2"],
        ),
    ],
)
async def test_cleanup_device_mqtt(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    discovery_topic: str,
    discovery_payload: str,
    entity_ids: list[str],
) -> None:
    """Test discovered device is cleaned up when removed through MQTT."""
    mqtt_mock = await mqtt_mock_entry()

    # set up an existing sensor first
    data = (
        '{ "device":{"identifiers":["0AFFD3"]},'
        '  "name": "sensor_base",'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique_base" }'
    )
    base_discovery_topic = "homeassistant/sensor/bla_base/config"
    base_entity_id = "sensor.none_sensor_base"
    async_fire_mqtt_message(hass, base_discovery_topic, data)
    await hass.async_block_till_done()

    # Verify the base entity has been created and it has a state
    base_device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "0AFFD3")}
    )
    assert base_device_entry is not None
    entity_entry = entity_registry.async_get(base_entity_id)
    assert entity_entry is not None
    state = hass.states.get(base_entity_id)
    assert state is not None

    async_fire_mqtt_message(hass, discovery_topic, discovery_payload)
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is not None
    for entity_id in entity_ids:
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None

        state = hass.states.get(entity_id)
        assert state is not None

    async_fire_mqtt_message(hass, discovery_topic, "")
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify device and registry entries are cleared
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is None

    for entity_id in entity_ids:
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is None

        # Verify state is removed
        state = hass.states.get(entity_id)
        assert state is None
        await hass.async_block_till_done()

    # Verify retained discovery topics have not been cleared again
    mqtt_mock.async_publish.assert_not_called()

    # Verify the base entity still exists and it has a state
    base_device_entry = device_registry.async_get_device(
        identifiers={("mqtt", "0AFFD3")}
    )
    assert base_device_entry is not None
    entity_entry = entity_registry.async_get(base_entity_id)
    assert entity_entry is not None
    state = hass.states.get(base_entity_id)
    assert state is not None


async def test_cleanup_device_mqtt_device_discovery(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test discovered device is cleaned up partly when removed through MQTT."""
    await mqtt_mock_entry()

    discovery_topic = "homeassistant/device/bla/config"
    discovery_payload = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "o": {"name": "foobar"},'
        '  "cmps": {"sens1": {'
        '  "p": "sensor",'
        '  "name": "sensor1",'
        '  "state_topic": "foobar/sensor1",'
        '  "unique_id": "unique1"'
        ' },"sens2": {'
        '  "p": "sensor",'
        '  "name": "sensor2",'
        '  "state_topic": "foobar/sensor2",'
        '  "unique_id": "unique2"'
        "}}}"
    )
    entity_ids = ["sensor.none_sensor1", "sensor.none_sensor2"]
    async_fire_mqtt_message(hass, discovery_topic, discovery_payload)
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is not None
    for entity_id in entity_ids:
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None

        state = hass.states.get(entity_id)
        assert state is not None

    # Do update and remove sensor 2 from device
    discovery_payload_update1 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "o": {"name": "foobar"},'
        '  "cmps": {"sens1": {'
        '  "p": "sensor",'
        '  "name": "sensor1",'
        '  "state_topic": "foobar/sensor1",'
        '  "unique_id": "unique1"'
        ' },"sens2": {'
        '  "p": "sensor"'
        "}}}"
    )
    async_fire_mqtt_message(hass, discovery_topic, discovery_payload_update1)
    await hass.async_block_till_done()
    state = hass.states.get(entity_ids[0])
    assert state is not None
    state = hass.states.get(entity_ids[1])
    assert state is None

    # Repeating the update
    async_fire_mqtt_message(hass, discovery_topic, discovery_payload_update1)
    await hass.async_block_till_done()
    state = hass.states.get(entity_ids[0])
    assert state is not None
    state = hass.states.get(entity_ids[1])
    assert state is None

    # Removing last sensor
    discovery_payload_update2 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "o": {"name": "foobar"},'
        '  "cmps": {"sens1": {'
        '  "p": "sensor"'
        ' },"sens2": {'
        '  "p": "sensor"'
        "}}}"
    )
    async_fire_mqtt_message(hass, discovery_topic, discovery_payload_update2)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    # Verify the device entry was removed with the last sensor
    assert device_entry is None
    for entity_id in entity_ids:
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is None

        state = hass.states.get(entity_id)
        assert state is None

    # Repeating the update
    async_fire_mqtt_message(hass, discovery_topic, discovery_payload_update2)
    await hass.async_block_till_done()

    # Clear the empty discovery payload and verify there was nothing to cleanup
    async_fire_mqtt_message(hass, discovery_topic, "")
    await hass.async_block_till_done()
    assert "No device components to cleanup" in caplog.text


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
            call("homeassistant/sensor/bla/config", None, 0, True),
            call("homeassistant/tag/bla/config", None, 0, True),
            call("homeassistant/device_automation/bla/config", None, 0, True),
        ],
        any_order=True,
    )


async def test_cleanup_device_multiple_config_entries_mqtt(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
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
    assert "KeyError:" not in caplog.text


async def test_discovery_expansion(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
    missing: list[str] = []
    regex = re.compile(r"(CONF_[a-zA-Z\d_]*) *= *[\'\"]([a-zA-Z\d_]*)[\'\"]")

    def _add_missing():
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

    await hass.async_add_executor_job(_add_missing)

    assert not missing


async def test_no_implicit_state_topic_switch(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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


@patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.UNSUBSCRIBE_COOLDOWN", 0.0)
@pytest.mark.parametrize(
    "reason", ["single_instance_allowed", "already_configured", "some_abort_error"]
)
async def test_mqtt_integration_discovery_flow_fitering_on_redundant_payload(
    hass: HomeAssistant, mqtt_client_mock: MqttMockPahoClient, reason: str
) -> None:
    """Check MQTT integration discovery starts a flow once."""
    flow_calls: list[MqttServiceInfo] = []

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> FlowResult:
            """Test mqtt step."""
            flow_calls.append(discovery_info)
            return self.async_abort(reason=reason)

    mock_platform(hass, "comp.config_flow", None)

    birth = asyncio.Event()

    @callback
    def wait_birth(msg: ReceiveMessage) -> None:
        """Handle birth message."""
        birth.set()

    entry = MockConfigEntry(domain=mqtt.DOMAIN, data=ENTRY_DEFAULT_BIRTH_MESSAGE)
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.mqtt.discovery.async_get_mqtt",
            return_value={"comp": ["comp/discovery/#"]},
        ),
        mock_config_flow("comp", TestFlow),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await mqtt.async_subscribe(hass, "homeassistant/status", wait_birth)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await birth.wait()

        assert ("comp/discovery/#", 0) in help_all_subscribe_calls(mqtt_client_mock)
        assert not mqtt_client_mock.unsubscribe.called
        mqtt_client_mock.reset_mock()
        assert len(flow_calls) == 0

        await hass.async_block_till_done(wait_background_tasks=True)
        async_fire_mqtt_message(hass, "comp/discovery/bla/config", "initial message")
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(flow_calls) == 1

        # A redundant message gets does not start a new flow
        await hass.async_block_till_done(wait_background_tasks=True)
        async_fire_mqtt_message(hass, "comp/discovery/bla/config", "initial message")
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(flow_calls) == 1

        # An updated message gets starts a new flow
        await hass.async_block_till_done(wait_background_tasks=True)
        async_fire_mqtt_message(hass, "comp/discovery/bla/config", "update message")
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(flow_calls) == 2


@patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0)
@patch("homeassistant.components.mqtt.client.UNSUBSCRIBE_COOLDOWN", 0.0)
async def test_mqtt_discovery_flow_starts_once(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    caplog: pytest.LogCaptureFixture,
    mock_mqtt_flow: config_entries.ConfigFlow,
    mqtt_data_flow_calls: list[MqttServiceInfo],
) -> None:
    """Check MQTT integration discovery starts a flow once.

    A flow should be started once after discovery,
    and after an entry was removed, to trigger re-discovery.
    """
    mock_integration(
        hass, MockModule(domain="comp", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_platform(hass, "comp.config_flow", None)

    birth = asyncio.Event()

    @callback
    def wait_birth(msg: ReceiveMessage) -> None:
        """Handle birth message."""
        birth.set()

    entry = MockConfigEntry(domain=mqtt.DOMAIN, data=ENTRY_DEFAULT_BIRTH_MESSAGE)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.mqtt.discovery.async_get_mqtt",
            return_value={"comp": ["comp/discovery/#"]},
        ),
        mock_config_flow("comp", mock_mqtt_flow),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await mqtt.async_subscribe(hass, "homeassistant/status", wait_birth)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await birth.wait()

        assert ("comp/discovery/#", 0) in help_all_subscribe_calls(mqtt_client_mock)

        # Test the initial flow
        async_fire_mqtt_message(hass, "comp/discovery/bla/config1", "initial message")
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(mqtt_data_flow_calls) == 1
        assert mqtt_data_flow_calls[0].topic == "comp/discovery/bla/config1"
        assert mqtt_data_flow_calls[0].payload == "initial message"

        # Test we can ignore updates if they are the same
        with caplog.at_level(logging.DEBUG):
            async_fire_mqtt_message(
                hass, "comp/discovery/bla/config1", "initial message"
            )
            await hass.async_block_till_done(wait_background_tasks=True)
            assert "Ignoring already processed discovery message" in caplog.text
            assert len(mqtt_data_flow_calls) == 1

        # Test we can apply updates
        async_fire_mqtt_message(hass, "comp/discovery/bla/config1", "update message")
        await hass.async_block_till_done(wait_background_tasks=True)

        assert len(mqtt_data_flow_calls) == 2
        assert mqtt_data_flow_calls[1].topic == "comp/discovery/bla/config1"
        assert mqtt_data_flow_calls[1].payload == "update message"

        # Test we set up multiple entries
        async_fire_mqtt_message(hass, "comp/discovery/bla/config2", "initial message")
        await hass.async_block_till_done(wait_background_tasks=True)

        assert len(mqtt_data_flow_calls) == 3
        assert mqtt_data_flow_calls[2].topic == "comp/discovery/bla/config2"
        assert mqtt_data_flow_calls[2].payload == "initial message"

        # Test we update multiple entries
        async_fire_mqtt_message(hass, "comp/discovery/bla/config2", "update message")
        await hass.async_block_till_done(wait_background_tasks=True)

        assert len(mqtt_data_flow_calls) == 4
        assert mqtt_data_flow_calls[3].topic == "comp/discovery/bla/config2"
        assert mqtt_data_flow_calls[3].payload == "update message"

        # Test an empty message triggers a flow to allow cleanup (if needed)
        async_fire_mqtt_message(hass, "comp/discovery/bla/config2", "")
        await hass.async_block_till_done(wait_background_tasks=True)

        assert len(mqtt_data_flow_calls) == 5
        assert mqtt_data_flow_calls[4].topic == "comp/discovery/bla/config2"
        assert mqtt_data_flow_calls[4].payload == ""

        # Cleanup the the second entry
        assert (
            entry := hass.config_entries.async_entry_for_domain_unique_id(
                "comp", "comp/discovery/bla/config2"
            )
        ) is not None
        await hass.config_entries.async_remove(entry.entry_id)
        assert len(hass.config_entries.async_entries(domain="comp")) == 1

        # Remove remaining entry1 and assert this triggers an
        # automatic re-discovery flow with latest config
        assert (
            entry := hass.config_entries.async_entry_for_domain_unique_id(
                "comp", "comp/discovery/bla/config1"
            )
        ) is not None
        assert entry.unique_id == "comp/discovery/bla/config1"
        await hass.config_entries.async_remove(entry.entry_id)
        assert len(hass.config_entries.async_entries(domain="comp")) == 0

        # Wait for re-discovery flow to complete
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(mqtt_data_flow_calls) == 6
        assert mqtt_data_flow_calls[5].topic == "comp/discovery/bla/config1"
        assert mqtt_data_flow_calls[5].payload == "update message"

        # Re-discovery triggered the config flow
        assert len(hass.config_entries.async_entries(domain="comp")) == 1

        assert not mqtt_client_mock.unsubscribe.called


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
        call("homeassistant/sensor/sbfspot_0/sbfspot_12345/config", None, 0, True)
        in mqtt_mock.async_publish.mock_calls
    )
    assert (
        call("homeassistant/sensor/sbfspot_0/sbfspot_12345_1/config", None, 0, True)
        in mqtt_mock.async_publish.mock_calls
    )


async def test_clean_up_registry_monitoring(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
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


@pytest.mark.parametrize(
    "signal_message",
    [
        MQTT_DISCOVERY_NEW,
        MQTT_DISCOVERY_UPDATED,
        MQTT_DISCOVERY_DONE,
    ],
)
async def test_discovery_dispatcher_signal_type_messages(
    hass: HomeAssistant, signal_message: SignalTypeFormat[MQTTDiscoveryPayload]
) -> None:
    """Test discovery dispatcher messages."""

    domain_id_tuple = ("sensor", "very_unique")
    test_data = {"name": "test", "state_topic": "test-topic"}
    calls = []

    def _callback(*args) -> None:
        calls.append(*args)

    unsub = async_dispatcher_connect(
        hass, signal_message.format(*domain_id_tuple), _callback
    )
    async_dispatcher_send(hass, signal_message.format(*domain_id_tuple), test_data)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0] == test_data
    unsub()


@pytest.mark.parametrize(
    ("discovery_topic", "discovery_payload", "entity_ids"),
    [
        (
            "homeassistant/device/bla/config",
            '{ "device":{"identifiers":["0AFFD2"]},'
            '  "o": {"name": "foobar"},'
            '  "state_topic": "foobar/sensor-shared",'
            '  "cmps": {"sens1": {'
            '  "platform": "sensor",'
            '  "name": "sensor1",'
            '  "unique_id": "unique1"'
            ' },"sens2": {'
            '  "platform": "sensor",'
            '  "name": "sensor2",'
            '  "unique_id": "unique2"'
            ' },"sens3": {'
            '  "platform": "sensor",'
            '  "name": "sensor3",'
            '  "state_topic": "foobar/sensor3",'
            '  "unique_id": "unique3"'
            "}}}",
            ["sensor.none_sensor1", "sensor.none_sensor2", "sensor.none_sensor3"],
        ),
    ],
)
async def test_shared_state_topic(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    discovery_topic: str,
    discovery_payload: str,
    entity_ids: list[str],
) -> None:
    """Test a shared state_topic can be used."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, discovery_topic, discovery_payload)
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_registry.async_get_device(identifiers={("mqtt", "0AFFD2")})
    assert device_entry is not None
    for entity_id in entity_ids:
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "foobar/sensor-shared", "New state")

    entity_id = entity_ids[0]
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "New state"
    entity_id = entity_ids[1]
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "New state"
    entity_id = entity_ids[2]
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "foobar/sensor3", "New state3")
    entity_id = entity_ids[2]
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "New state3"


@pytest.mark.parametrize("single_configs", [copy.deepcopy(TEST_SINGLE_CONFIGS)])
async def test_discovery_with_late_via_device_discovery(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    tag_mock: AsyncMock,
    single_configs: list[tuple[str, dict[str, Any]]],
) -> None:
    """Test a via device is available and the discovery of the via device is late."""
    await mqtt_mock_entry()

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    via_device_entry = device_registry.async_get_device(
        {("mqtt", "id_via_very_unique")}
    )
    assert via_device_entry is None
    # Discovery single config schema
    for discovery_topic, config in single_configs:
        config["device"]["via_device"] = "id_via_very_unique"
        payload = json.dumps(config)
        async_fire_mqtt_message(
            hass,
            discovery_topic,
            payload,
        )
        via_device_entry = device_registry.async_get_device(
            {("mqtt", "id_via_very_unique")}
        )
        assert via_device_entry is not None
        assert via_device_entry.name is None

    await hass.async_block_till_done()

    # Now discover the via device (a switch)
    via_device_config = {
        "name": None,
        "command_topic": "test-switch-topic",
        "unique_id": "very_unique_switch",
        "device": {"identifiers": ["id_via_very_unique"], "name": "My Switch"},
    }
    payload = json.dumps(via_device_config)
    via_device_discovery_topic = "homeassistant/switch/very_unique/config"
    async_fire_mqtt_message(
        hass,
        via_device_discovery_topic,
        payload,
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    via_device_entry = device_registry.async_get_device(
        {("mqtt", "id_via_very_unique")}
    )
    assert via_device_entry is not None
    assert via_device_entry.name == "My Switch"

    await help_check_discovered_items(hass, device_registry, tag_mock)


@pytest.mark.parametrize("single_configs", [copy.deepcopy(TEST_SINGLE_CONFIGS)])
async def test_discovery_with_late_via_device_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    tag_mock: AsyncMock,
    single_configs: list[tuple[str, dict[str, Any]]],
) -> None:
    """Test a via device is available and the discovery of the via device is is set via an update."""
    await mqtt_mock_entry()

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    via_device_entry = device_registry.async_get_device(
        {("mqtt", "id_via_very_unique")}
    )
    assert via_device_entry is None
    # Discovery single config schema without via device
    for discovery_topic, config in single_configs:
        payload = json.dumps(config)
        async_fire_mqtt_message(
            hass,
            discovery_topic,
            payload,
        )
        via_device_entry = device_registry.async_get_device(
            {("mqtt", "id_via_very_unique")}
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()
        assert via_device_entry is None

    # Resend the discovery update to set the via device
    for discovery_topic, config in single_configs:
        config["device"]["via_device"] = "id_via_very_unique"
        payload = json.dumps(config)
        async_fire_mqtt_message(
            hass,
            discovery_topic,
            payload,
        )
        via_device_entry = device_registry.async_get_device(
            {("mqtt", "id_via_very_unique")}
        )
        assert via_device_entry is not None
        assert via_device_entry.name is None

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Now discover the via device (a switch)
    via_device_config = {
        "name": None,
        "command_topic": "test-switch-topic",
        "unique_id": "very_unique_switch",
        "device": {"identifiers": ["id_via_very_unique"], "name": "My Switch"},
    }
    payload = json.dumps(via_device_config)
    via_device_discovery_topic = "homeassistant/switch/very_unique/config"
    async_fire_mqtt_message(
        hass,
        via_device_discovery_topic,
        payload,
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    via_device_entry = device_registry.async_get_device(
        {("mqtt", "id_via_very_unique")}
    )
    assert via_device_entry is not None
    assert via_device_entry.name == "My Switch"

    await help_check_discovered_items(hass, device_registry, tag_mock)
