"""Tests for the llm helpers."""

from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from voluptuous_openapi import UNSUPPORTED

from homeassistant.core import Context, HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    floor_registry as fr,
    intent,
    llm,
)
from homeassistant.util.color import color_name_to_rgb


def test_async_register(hass: HomeAssistant) -> None:
    """Test registering an llm tool and verifying it is stored correctly."""
    tool = llm.Tool("test_tool", "test_description")

    llm.async_register_tool(hass, tool)

    assert hass.data[llm.DATA_KEY]["test_tool"] == tool
    assert list(llm.async_get_tools(hass)) == [tool]


def test_async_register_overwrite(hass: HomeAssistant) -> None:
    """Test registering multiple tools with the same name, ensuring the second time an exception is raised."""
    tool1 = llm.Tool("test_tool", "test_tool_1")
    tool2 = llm.Tool("test_tool", "test_tool_2")

    llm.async_register_tool(hass, tool1)
    with pytest.raises(HomeAssistantError):
        llm.async_register_tool(hass, tool2)

    assert hass.data[llm.DATA_KEY]["test_tool"] == tool1
    assert list(llm.async_get_tools(hass)) == [tool1]


def test_async_remove(hass: HomeAssistant) -> None:
    """Test removing a tool and verifying it is no longer present in the Home Assistant data."""
    tool = llm.Tool("test_tool", "test_description")

    llm.async_register_tool(hass, tool)
    llm.async_remove_tool(hass, "test_tool")

    assert "test_tool" not in hass.data[llm.DATA_KEY]
    assert list(llm.async_get_tools(hass)) == []


def test_async_remove_no_existing_entry(hass: HomeAssistant) -> None:
    """Test the removal of a non-existing tool from Home Assistant's data."""
    tool = llm.Tool("test_tool", "test_description")
    llm.async_register_tool(hass, tool)

    llm.async_remove_tool(hass, "test_tool2")

    assert "test_tool" in hass.data[llm.DATA_KEY]
    assert "test_tool2" not in hass.data[llm.DATA_KEY]
    assert list(llm.async_get_tools(hass)) == [tool]


def test_async_remove_no_existing(hass: HomeAssistant) -> None:
    """Test the removal of a tool where no config exists."""

    llm.async_remove_tool(hass, "test_tool2")
    # simply shouldn't cause an exception

    assert llm.DATA_KEY not in hass.data
    assert list(llm.async_get_tools(hass)) == []


async def test_call_tool(hass: HomeAssistant) -> None:
    """Test calling an llm tool."""
    tool = AsyncMock()
    tool.name = "test_tool"
    tool.async_call.return_value = {"result": "test_response"}

    llm.async_register_tool(hass, tool)
    test_context = Context()

    response = await llm.async_call_tool(
        hass,
        "test_platform",
        "test_tool",
        '{"test_arg": "test_value"}',
        "test_text",
        test_context,
        "en",
        "test_agent",
        "test_conversation_id",
        "test_device_id",
        "test_assistant",
    )

    tool.async_call.assert_awaited_once_with(
        hass,
        "test_platform",
        "test_text",
        test_context,
        "en",
        "test_agent",
        "test_conversation_id",
        "test_device_id",
        "test_assistant",
        test_arg="test_value",
    )
    assert response == '{"result": "test_response"}'


async def test_call_tool_exception(hass: HomeAssistant) -> None:
    """Test calling an llm tool ith exception."""
    tool = AsyncMock()
    tool.name = "test_tool"
    tool.async_call.side_effect = RuntimeError("Test exception")

    llm.async_register_tool(hass, tool)
    test_context = Context()

    response = await llm.async_call_tool(
        hass,
        "test_platform",
        "test_tool",
        '{"test_arg": "test_value"}',
        "test_text",
        test_context,
        "en",
        "test_agent",
        "test_conversation_id",
        "test_device_id",
        "test_assistant",
    )

    tool.async_call.assert_awaited_once_with(
        hass,
        "test_platform",
        "test_text",
        test_context,
        "en",
        "test_agent",
        "test_conversation_id",
        "test_device_id",
        "test_assistant",
        test_arg="test_value",
    )
    assert response == '{"error": "RuntimeError", "error_text": "Test exception"}'


async def test_call_tool_no_existing(hass: HomeAssistant) -> None:
    """Test calling an llm tool where no config exists."""
    response = await llm.async_call_tool(
        hass,
        "test_platform",
        "test_tool",
    )

    assert response == '{"error": "KeyError", "error_text": "\'test_tool\'"}'


def test_custom_serializer() -> None:
    """Test custom serializer."""
    assert llm.custom_serializer(cv.string) == {"type": "string"}
    assert llm.custom_serializer(cv.boolean) == {"type": "boolean"}
    assert llm.custom_serializer(color_name_to_rgb) == {"type": "string"}
    assert llm.custom_serializer(cv.multi_select(["alpha", "beta"])) == {
        "enum": ["alpha", "beta"]
    }
    assert llm.custom_serializer(lambda x: x) == {}
    assert llm.custom_serializer("unsupported") == UNSUPPORTED


async def test_intent_tool(hass: HomeAssistant) -> None:
    """Test llm.IntentTool class."""
    tool = llm.IntentTool("test_intent")
    assert tool.name == "test_intent"
    assert tool.description == "Execute Home Assistant test_intent intent"
    assert tool.parameters == llm.NO_PARAMETERS
    assert str(tool) == "<IntentTool - test_intent>"

    test_context = Context()
    intent_response = intent.IntentResponse("*")
    intent_response.matched_states = [State("light.matched", "on")]
    intent_response.unmatched_states = [State("light.unmatched", "on")]
    with patch(
        "homeassistant.helpers.intent.async_handle", return_value=intent_response
    ) as mock_intent_handle:
        response = await tool.async_call(
            hass,
            "test_platform",
            "test_text",
            test_context,
            "*",
            "test_agent",
            "test_conversation_id",
            "test_device_id",
            "test_assistant",
            area="kitchen",
            floor="ground_floor",
        )

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
    """Test llm.IntentTool call with area and floor."""
    tool = llm.IntentTool(
        "test_intent",
        vol.Schema(
            {
                vol.Optional("test_arg", description="test arg description"): cv.string,
                vol.Optional("area"): cv.string,
                vol.Optional("floor"): cv.string,
            },
        ),
    )
    assert tool.description == "Execute Home Assistant test_intent intent"
    assert tool.parameters == {
        "type": "object",
        "properties": {
            "test_arg": {"type": "string", "description": "test arg description"},
            "area": {"type": "string"},
            "floor": {"type": "string"},
        },
        "required": [],
    }

    area_kitchen = area_registry.async_get_or_create("kitchen")
    floor_1 = floor_registry.async_create("first floor", aliases={"ground floor"})
    area_kitchen = area_registry.async_update(
        area_kitchen.id, aliases={"küche"}, floor_id=floor_1.floor_id
    )
    area_registry.async_get_or_create("bedroom")
    floor_registry.async_create("second floor")

    test_context = Context()
    with patch(
        "homeassistant.helpers.intent.async_handle",
        return_value=intent.IntentResponse("*"),
    ) as mock_intent_handle:
        response = await tool.async_call(
            hass,
            "test_platform",
            "test_text",
            test_context,
            "*",
            "test_agent",
            "test_conversation_id",
            "test_device_id",
            "test_assistant",
            test_arg="test_value",
            area="küche",
            floor="ground floor",
        )

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
