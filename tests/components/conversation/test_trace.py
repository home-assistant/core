"""Test for the conversation traces."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import async_mock_service

from homeassistant.components import conversation
from homeassistant.components.conversation import DOMAIN, trace
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_OFF
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.setup import async_setup_component


@pytest.fixture
async def init_components(hass: HomeAssistant):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "intent", {})


async def test_converation_trace(
    hass: HomeAssistant,
    init_components: None,
    sl_setup: None,
) -> None:
    """Test tracing a conversation."""
    await conversation.async_converse(
        hass, "add apples to my shopping list", None, Context()
    )

    traces = trace.async_get_traces()
    assert traces
    last_trace = traces[-1].as_dict()
    assert last_trace.get("events")
    assert len(last_trace.get("events")) == 3
    trace_event = last_trace["events"][0]
    assert (
        trace_event.get("event_type") == trace.ConversationTraceEventType.ASYNC_PROCESS
    )
    assert trace_event.get("data")
    assert trace_event["data"].get("text") == "add apples to my shopping list"
    assert last_trace.get("result")
    assert (
        last_trace["result"]
        .get("response", {})
        .get("speech", {})
        .get("plain", {})
        .get("speech")
        == "Added apples"
    )

    trace_event = last_trace["events"][1]
    assert trace_event.get("event_type") == trace.ConversationTraceEventType.TOOL_CALL
    assert trace_event.get("data") == {
        "intent_name": "HassListAddItem",
        "slots": {
            "name": "Shopping list",
            "item": "apples",
        },
    }

    trace_event = last_trace["events"][2]
    assert (
        trace_event.get("event_type") == trace.ConversationTraceEventType.TURN_CONTENT
    )
    assert [content["role"] for content in trace_event["data"]["content"]] == [
        "user",
        "assistant",
        "tool_result",
        "assistant",
    ]


@pytest.mark.usefixtures("init_components")
async def test_conversation_trace_name_fallback(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a candidate that finds no targets leaves no tool call."""
    async_mock_service(hass, "light", "turn_on")
    area_kitchen = area_registry.async_get_or_create("kitchen")
    area_bedroom = area_registry.async_get_or_create("bedroom")

    light = entity_registry.async_get_or_create(
        "light", "demo", "lights", original_name="lights"
    )
    entity_registry.async_update_entity(light.entity_id, area_id=area_kitchen.id)
    hass.states.async_set(light.entity_id, STATE_OFF, {ATTR_FRIENDLY_NAME: "lights"})

    satellite = entity_registry.async_get_or_create("assist_satellite", "demo", "sat")
    entity_registry.async_update_entity(satellite.entity_id, area_id=area_bedroom.id)

    await conversation.async_converse(
        hass,
        "turn on the lights",
        None,
        Context(),
        satellite_id=satellite.entity_id,
    )

    events = trace.async_get_traces()[-1].as_dict()["events"]
    assert [
        event["data"]
        for event in events
        if event["event_type"] == trace.ConversationTraceEventType.TOOL_CALL
    ] == [{"intent_name": "HassTurnOn", "slots": {"name": "lights"}}]


async def test_converation_trace_uncaught_error(
    hass: HomeAssistant,
    init_components: None,
    sl_setup: None,
) -> None:
    """Test tracing a conversation that raises an uncaught error."""
    with (
        patch(
            "homeassistant.components.conversation.default_agent.DefaultAgent.async_process",
            side_effect=ValueError("Unexpected error"),
        ),
        pytest.raises(ValueError),
    ):
        await conversation.async_converse(
            hass, "add apples to my shopping list", None, Context()
        )

    traces = trace.async_get_traces()
    assert traces
    last_trace = traces[-1].as_dict()
    assert last_trace.get("events")
    assert len(last_trace.get("events")) == 1
    trace_event = last_trace["events"][0]
    assert (
        trace_event.get("event_type") == trace.ConversationTraceEventType.ASYNC_PROCESS
    )
    assert last_trace.get("error") == "Unexpected error"
    assert not last_trace.get("result")


async def test_converation_trace_homeassistant_error(
    hass: HomeAssistant,
    init_components: None,
    sl_setup: None,
) -> None:
    """Test tracing a conversation with a HomeAssistant error."""
    with (
        patch(
            "homeassistant.components.conversation.default_agent.DefaultAgent.async_process",
            side_effect=HomeAssistantError("Failed to talk to agent"),
        ),
    ):
        await conversation.async_converse(
            hass, "add apples to my shopping list", None, Context()
        )

    traces = trace.async_get_traces()
    assert traces
    last_trace = traces[-1].as_dict()
    assert last_trace.get("events")
    assert len(last_trace.get("events")) == 1
    trace_event = last_trace["events"][0]
    assert (
        trace_event.get("event_type") == trace.ConversationTraceEventType.ASYNC_PROCESS
    )
    result = last_trace.get("result")
    assert result
    assert result["response"]["speech"]["plain"]["speech"] == "Failed to talk to agent"
