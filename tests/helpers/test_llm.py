"""Tests for the llm helpers."""

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.core import Context, HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    floor_registry as fr,
    intent,
    llm,
)


async def test_call_tool_no_existing(hass: HomeAssistant) -> None:
    """Test calling an llm tool where no config exists."""
    with pytest.raises(HomeAssistantError):
        await llm.async_call_tool(
            hass,
            llm.ToolInput(
                "test_tool",
                {},
                "test_platform",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ),
        )


async def test_intent_tool(hass: HomeAssistant) -> None:
    """Test IntentTool class."""
    schema = vol.Schema(
        {
            vol.Optional("area"): cv.string,
            vol.Optional("floor"): cv.string,
        }
    )

    intent_handler = intent.IntentHandler()
    intent_handler.intent_type = "test_intent"
    intent_handler.slot_schema = schema

    intent.async_register(hass, intent_handler)

    assert len(list(llm.async_get_tools(hass))) == 1
    tool = list(llm.async_get_tools(hass))[0]
    assert tool.name == "test_intent"
    assert tool.description == "Execute Home Assistant test_intent intent"
    assert tool.parameters == schema
    assert str(tool) == "<IntentTool - test_intent>"

    test_context = Context()
    intent_response = intent.IntentResponse("*")
    intent_response.matched_states = [State("light.matched", "on")]
    intent_response.unmatched_states = [State("light.unmatched", "on")]
    tool_input = llm.ToolInput(
        tool_name="test_intent",
        tool_args={"area": "kitchen", "floor": "ground_floor"},
        platform="test_platform",
        context=test_context,
        user_prompt="test_text",
        language="*",
        agent_id="test_agent",
        conversation_id="test_conversation_id",
        device_id="test_device_id",
        assistant="test_assistant",
    )

    with patch(
        "homeassistant.helpers.intent.async_handle", return_value=intent_response
    ) as mock_intent_handle:
        response = await llm.async_call_tool(hass, tool_input)

    mock_intent_handle.assert_awaited_once_with(
        hass,
        "test_platform",
        "test_intent",
        {
            "area": {"value": "kitchen", "text": "kitchen"},
            "floor": {"value": "ground_floor", "text": "ground_floor"},
        },
        "test_text",
        test_context,
        "*",
        "test_assistant",
    )
    assert response == {
        "card": {},
        "data": {
            "failed": [],
            "success": [],
            "targets": [],
        },
        "language": "*",
        "response_type": "action_done",
        "speech": {},
    }


async def test_intent_tool_with_area_and_floor(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test IntentTool call with area and floor."""
    schema = vol.Schema(
        {
            vol.Optional("test_arg", description="test arg description"): cv.string,
            vol.Optional("area"): cv.string,
            vol.Optional("floor"): cv.string,
        }
    )

    intent_handler = intent.IntentHandler()
    intent_handler.intent_type = "test_intent"
    intent_handler.slot_schema = schema

    intent.async_register(hass, intent_handler)

    assert len(list(llm.async_get_tools(hass))) == 1
    tool = list(llm.async_get_tools(hass))[0]
    assert tool.name == "test_intent"
    assert tool.description == "Execute Home Assistant test_intent intent"
    assert tool.parameters == schema

    area_kitchen = area_registry.async_get_or_create("kitchen")
    floor_1 = floor_registry.async_create("first floor", aliases={"ground floor"})
    area_kitchen = area_registry.async_update(
        area_kitchen.id, aliases={"küche"}, floor_id=floor_1.floor_id
    )
    area_registry.async_get_or_create("bedroom")
    floor_registry.async_create("second floor")

    test_context = Context()

    tool_input = llm.ToolInput(
        tool_name="test_intent",
        tool_args={"test_arg": "test_value", "area": "küche", "floor": "ground floor"},
        platform="test_platform",
        context=test_context,
        user_prompt="test_text",
        language="*",
        agent_id="test_agent",
        conversation_id="test_conversation_id",
        device_id="test_device_id",
        assistant="test_assistant",
    )
    with patch(
        "homeassistant.helpers.intent.async_handle",
        return_value=intent.IntentResponse("*"),
    ) as mock_intent_handle:
        response = await llm.async_call_tool(hass, tool_input)

    mock_intent_handle.assert_awaited_once_with(
        hass,
        "test_platform",
        "test_intent",
        {
            "test_arg": {"value": "test_value"},
            "area": {"value": "kitchen", "text": "kitchen"},
            "floor": {"value": "first_floor", "text": "first floor"},
        },
        "test_text",
        test_context,
        "*",
        "test_assistant",
    )
    assert response == {
        "card": {},
        "data": {
            "failed": [],
            "success": [],
            "targets": [],
        },
        "language": "*",
        "response_type": "action_done",
        "speech": {},
    }
