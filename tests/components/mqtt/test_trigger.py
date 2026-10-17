"""The tests for the MQTT automation."""

import asyncio
from datetime import timedelta
from unittest.mock import ANY

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import automation
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, SERVICE_TURN_OFF
from homeassistant.core import Context, HassJobType, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr, script
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_mqtt_message,
    async_fire_time_changed,
    mock_component,
)
from tests.typing import MqttMockHAClient, MqttMockHAClientGenerator

MOTION_ENTITY_ID = "binary_sensor.motion"
ROOM_ENTITY_ID = "sensor.room"


@pytest.fixture(autouse=True)
async def setup_comp(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> MqttMockHAClient:
    """Initialize components."""
    mock_component(hass, "group")
    return await mqtt_mock_entry()


async def test_if_fires_on_topic_match(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test if message is fired on topic match."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "mqtt", "topic": "test-topic"},
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": "{{ trigger.platform }} - {{ trigger.topic }} - "
                        "{{ trigger.payload }} - {{ trigger.payload_json.hello }} - "
                        "{{ trigger.id }}"
                    },
                },
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic", '{ "hello": "world" }')
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert (
        service_calls[0].data["some"]
        == 'mqtt - test-topic - { "hello": "world" } - world - 0'
    )

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    assert len(service_calls) == 2

    async_fire_mqtt_message(hass, "test-topic", "test_payload")
    await hass.async_block_till_done()
    assert len(service_calls) == 2


async def test_if_fires_on_topic_and_payload_match(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test if message is fired on topic and payload match."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test-topic",
                    "payload": "hello",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic", "hello")
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_on_topic_and_payload_match2(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test if message is fired on topic and payload match.

    Make sure a payload which would render as a non string can still be matched.
    """
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test-topic",
                    "payload": "0",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic", "0")
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_on_templated_topic_and_payload_match(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test if message is fired on templated topic and payload match."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test-topic-{{ sqrt(16)|round }}",
                    "payload": '{{ "foo"|regex_replace("foo", "bar") }}',
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic-", "foo")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    async_fire_mqtt_message(hass, "test-topic-4", "foo")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    async_fire_mqtt_message(hass, "test-topic-4", "bar")
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_on_payload_template(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test if message is fired on templated topic and payload match."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test-topic",
                    "payload": "hello",
                    "value_template": "{{ value_json.wanted_key }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic", "hello")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    async_fire_mqtt_message(hass, "test-topic", '{"unwanted_key":"hello"}')
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    async_fire_mqtt_message(hass, "test-topic", '{"wanted_key":"hello"}')
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_templated_topic_follows_state(
    hass: HomeAssistant, service_calls: list[ServiceCall], setup_comp
) -> None:
    """Test a templated topic moves to a new topic when a state changes."""
    hass.states.async_set(ROOM_ENTITY_ID, "kitchen")
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test/{{ states('sensor.room') }}",
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {"topic": "{{ trigger.topic }}"},
                },
            }
        },
    )

    async_fire_mqtt_message(hass, "test/hallway", "hello")
    async_fire_mqtt_message(hass, "test/kitchen", "hello")
    await hass.async_block_till_done()
    assert [call.data["topic"] for call in service_calls] == ["test/kitchen"]

    hass.states.async_set(ROOM_ENTITY_ID, "hallway")
    await hass.async_block_till_done()
    setup_comp.async_subscribe.assert_called_with(
        "test/hallway", ANY, 0, "utf-8", HassJobType.Callback
    )

    async_fire_mqtt_message(hass, "test/kitchen", "hello")
    async_fire_mqtt_message(hass, "test/hallway", "hello")
    await hass.async_block_till_done()
    assert [call.data["topic"] for call in service_calls] == [
        "test/kitchen",
        "test/hallway",
    ]

    # The room changes, but the topic does not: no new subscription.
    setup_comp.async_subscribe.reset_mock()
    hass.states.async_set(ROOM_ENTITY_ID, "hallway", {"floor": "ground"})
    await hass.async_block_till_done()
    setup_comp.async_subscribe.assert_not_called()


async def test_templated_topic_follows_device_rename(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a topic built from a device name follows a rename of the device."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "remote")},
        name="Kitchen remote",
    )
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger_variables": {"remote": device.id},
                "trigger": {
                    "platform": "mqtt",
                    "topic": "zigbee2mqtt/{{ device_attr(remote, 'name') }}/action",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_mqtt_message(hass, "zigbee2mqtt/Kitchen remote/action", "single")
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    device_registry.async_update_device(device.id, name="Hallway remote")
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "zigbee2mqtt/Kitchen remote/action", "single")
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    async_fire_mqtt_message(hass, "zigbee2mqtt/Hallway remote/action", "single")
    await hass.async_block_till_done()
    assert len(service_calls) == 2


@pytest.mark.parametrize(
    ("topic", "initial_room", "new_room", "current_topic", "error"),
    [
        pytest.param(
            "test/{{ states('sensor.room') }}",
            "kitchen",
            "kitchen#",
            "test/kitchen",
            "Invalid MQTT trigger topic 'test/kitchen#' in automation 0,"
            " keeping topic 'test/kitchen'",
            id="invalid_topic",
        ),
        pytest.param(
            "test/{{ states('sensor.room') | int }}",
            "1",
            "kitchen",
            "test/1",
            "Error rendering MQTT trigger topic in automation 0, keeping topic"
            " 'test/1'",
            id="render_error",
        ),
    ],
)
async def test_templated_topic_keeps_subscription_on_error(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    caplog: pytest.LogCaptureFixture,
    topic: str,
    initial_room: str,
    new_room: str,
    current_topic: str,
    error: str,
) -> None:
    """Test a topic that fails to re-render keeps the current subscription."""
    hass.states.async_set(ROOM_ENTITY_ID, initial_room)
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "mqtt", "topic": topic},
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(ROOM_ENTITY_ID, new_room)
    await hass.async_block_till_done()
    assert error in caplog.text

    async_fire_mqtt_message(hass, current_topic, "hello")
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_templated_topic_initial_render_error(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    caplog: pytest.LogCaptureFixture,
    setup_comp,
) -> None:
    """Test a topic that fails to render at setup does not attach the trigger."""
    hass.states.async_set(ROOM_ENTITY_ID, "kitchen")
    setup_comp.async_subscribe.reset_mock()
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test/{{ states('sensor.room') | int }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    assert "int got invalid input 'kitchen'" in caplog.text
    assert "when setting up triggers for automation 0" in caplog.text

    # A later state that renders fine does not attach the trigger.
    hass.states.async_set(ROOM_ENTITY_ID, "1")
    await hass.async_block_till_done()
    setup_comp.async_subscribe.assert_not_called()


async def test_templated_topic_change_keeps_other_triggers(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test moving the topic does not reset a pending for on another trigger."""
    hass.states.async_set(ROOM_ENTITY_ID, "kitchen")
    hass.states.async_set(MOTION_ENTITY_ID, "off")
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": [
                    {
                        "platform": "mqtt",
                        "topic": "test/{{ states('sensor.room') }}",
                    },
                    {
                        "platform": "state",
                        "entity_id": MOTION_ENTITY_ID,
                        "to": "on",
                        "for": {"seconds": 5},
                    },
                ],
                "action": {
                    "service": "test.automation",
                    "data_template": {"platform": "{{ trigger.platform }}"},
                },
            }
        },
    )

    hass.states.async_set(MOTION_ENTITY_ID, "on")
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    hass.states.async_set(ROOM_ENTITY_ID, "hallway")
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [call.data["platform"] for call in service_calls] == ["state"]

    async_fire_mqtt_message(hass, "test/hallway", "hello")
    await hass.async_block_till_done()
    assert [call.data["platform"] for call in service_calls] == ["state", "mqtt"]


async def test_templated_topic_stops_when_automation_turned_off(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    setup_comp,
) -> None:
    """Test turning off the automation unsubscribes and stops tracking."""
    hass.states.async_set(ROOM_ENTITY_ID, "kitchen")
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test/{{ states('sensor.room') }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    setup_comp.async_subscribe.reset_mock()

    hass.states.async_set(ROOM_ENTITY_ID, "hallway")
    await hass.async_block_till_done()
    setup_comp.async_subscribe.assert_not_called()

    async_fire_mqtt_message(hass, "test/kitchen", "hello")
    async_fire_mqtt_message(hass, "test/hallway", "hello")
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_templated_topic_in_wait_for_trigger(hass: HomeAssistant) -> None:
    """Test a templated topic in a wait uses run variables and follows states."""
    hass.states.async_set(ROOM_ENTITY_ID, "kitchen")
    events = async_capture_events(hass, "test_done")
    sequence = await script.async_validate_actions_config(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"variables": {"prefix": "home"}},
                {
                    "alias": "wait step",
                    "wait_for_trigger": {
                        "platform": "mqtt",
                        "topic": "{{ prefix }}/{{ states('sensor.room') }}",
                    },
                },
                {
                    "event": "test_done",
                    "event_data": {"topic": "{{ wait.trigger.topic }}"},
                },
            ]
        ),
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    wait_started = asyncio.Event()
    script_obj.change_listener = wait_started.set

    hass.async_create_task(script_obj.async_run(context=Context()))
    await asyncio.wait_for(wait_started.wait(), 1)

    hass.states.async_set(ROOM_ENTITY_ID, "hallway")
    async_fire_mqtt_message(hass, "home/kitchen", "hello")
    async_fire_mqtt_message(hass, "home/hallway", "hello")
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert [event.data["topic"] for event in events] == ["home/hallway"]


async def test_if_not_fires_on_topic_but_no_payload_match(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test if message is not fired on topic but no payload."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "mqtt",
                    "topic": "test-topic",
                    "payload": "hello",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic", "no-hello")
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_encoding_default(
    hass: HomeAssistant, service_calls: list[ServiceCall], setup_comp
) -> None:
    """Test default encoding."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "mqtt", "topic": "test-topic"},
                "action": {"service": "test.automation"},
            }
        },
    )

    setup_comp.async_subscribe.assert_called_with(
        "test-topic", ANY, 0, "utf-8", HassJobType.Callback
    )


async def test_encoding_custom(
    hass: HomeAssistant, service_calls: list[ServiceCall], setup_comp
) -> None:
    """Test default encoding."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "mqtt", "topic": "test-topic", "encoding": ""},
                "action": {"service": "test.automation"},
            }
        },
    )

    setup_comp.async_subscribe.assert_called_with(
        "test-topic", ANY, 0, None, HassJobType.Callback
    )
