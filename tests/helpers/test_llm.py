"""Tests for the llm helpers."""

from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from voluptuous_openapi import UNSUPPORTED

from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    entity_registry as er,
    floor_registry as fr,
    intent,
    llm,
)
from homeassistant.util.color import color_name_to_rgb


async def test_tool() -> None:
    """Test llm.Tool class."""
    test_parameters = {
        "type": "object",
        "properties": {
            "test_arg": {
                "type": "integer",
                "description": "Test arg description",
            },
        },
        "required": ["test_arg"],
    }
    tool = llm.Tool("test_name", "test_description", test_parameters)
    assert tool.name == "test_name"
    assert tool.description == "test_description"
    assert tool.parameters == test_parameters
    assert str(tool) == "<Tool - test_name>"
    with pytest.raises(NotImplementedError):
        await tool.async_call(None, None, None, None, None, None, None, None)


def test_async_register(hass: HomeAssistant) -> None:
    """Test registering an llm tool and verifying it is stored correctly."""
    tool = llm.Tool("test_tool", "test_description")

    llm.async_register_tool(hass, tool)

    assert hass.data[llm.DATA_KEY]["test_tool"] == tool
    assert list(llm.async_get_tools(hass)) == [tool]


def test_async_register_overwrite(hass: HomeAssistant) -> None:
    """Test registering multiple tools with the same name, ensuring the last one overwrites the previous one and a warning is emitted."""
    tool1 = llm.Tool("test_tool", "test_tool_1")
    tool2 = llm.Tool("test_tool", "test_tool_2")

    with patch.object(llm._LOGGER, "warning") as mock_warning:
        llm.async_register_tool(hass, tool1)
        llm.async_register_tool(hass, tool2)

        mock_warning.assert_called_once_with(
            "Tool %s is being overwritten by %s", "test_tool", tool2
        )

    assert hass.data[llm.DATA_KEY]["test_tool"] == tool2
    assert list(llm.async_get_tools(hass)) == [tool2]


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
        "test_assistant",
        "test_conversation_id",
        "test_device_id",
    )

    tool.async_call.assert_awaited_once_with(
        hass,
        "test_platform",
        "test_text",
        test_context,
        "en",
        "test_assistant",
        "test_conversation_id",
        "test_device_id",
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
        "test_assistant",
        "test_conversation_id",
        "test_device_id",
    )

    tool.async_call.assert_awaited_once_with(
        hass,
        "test_platform",
        "test_text",
        test_context,
        "en",
        "test_assistant",
        "test_conversation_id",
        "test_device_id",
        test_arg="test_value",
    )
    assert response == '{"error": "RuntimeError", "error_text": "Test exception"}'


def test_format_state(hass: HomeAssistant) -> None:
    """Test foratting of an entity state."""
    state1 = State(
        "light.kitchen", "on", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )

    assert llm._format_state(hass, state1) == {
        "name": "kitchen light",
        "entity_id": "light.kitchen",
        "state": "on",
        "last_changed": "0 seconds ago",
    }


def test_format_state_with_attributes(hass: HomeAssistant) -> None:
    """Test foratting of an entity state with attributes."""
    state1 = State(
        "light.kitchen",
        "on",
        attributes={
            ATTR_FRIENDLY_NAME: "kitchen light",
            "extra_attr": "filtered out",
            "brightness": "100",
        },
    )

    assert llm._format_state(hass, state1) == {
        "name": "kitchen light",
        "entity_id": "light.kitchen",
        "state": "on",
        "last_changed": "0 seconds ago",
        "attributes": {"brightness": "100"},
    }


def test_format_state_with_alias(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test foratting of an entity state with an alias assigned in entity registry."""
    state1 = State(
        "light.kitchen", "on", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )
    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="kitchen"
    )
    entity_registry.async_update_entity(state1.entity_id, aliases={"küchenlicht"})

    assert llm._format_state(hass, state1) == {
        "name": "kitchen light",
        "entity_id": "light.kitchen",
        "state": "on",
        "last_changed": "0 seconds ago",
        "aliases": ["küchenlicht"],
    }


def test_format_state_with_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test foratting of an entity state with area assigned in area registry."""
    state1 = State(
        "light.kitchen", "on", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )
    area_kitchen = area_registry.async_get_or_create("kitchen")
    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="kitchen"
    )
    entity_registry.async_update_entity(state1.entity_id, area_id=area_kitchen.id)

    assert llm._format_state(hass, state1) == {
        "name": "kitchen light",
        "entity_id": "light.kitchen",
        "state": "on",
        "last_changed": "0 seconds ago",
        "area": "kitchen",
    }


def test_format_state_with_floor(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test foratting of an entity state with area and a floor assigned in floor registry."""
    state1 = State(
        "light.kitchen", "on", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )

    area_kitchen = area_registry.async_get_or_create("kitchen")
    floor_1 = floor_registry.async_create("first floor", aliases={"ground floor"})
    area_kitchen = area_registry.async_update(
        area_kitchen.id, floor_id=floor_1.floor_id
    )
    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="kitchen"
    )
    entity_registry.async_update_entity(state1.entity_id, area_id=area_kitchen.id)

    assert llm._format_state(hass, state1) == {
        "name": "kitchen light",
        "entity_id": "light.kitchen",
        "state": "on",
        "last_changed": "0 seconds ago",
        "area": "kitchen",
        "floor": "first floor",
    }


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
            "test_assistant",
            "test_conversation_id",
            "test_device_id",
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
            "matched_states": [
                {
                    "entity_id": "light.matched",
                    "last_changed": "0 seconds ago",
                    "name": "matched",
                    "state": "on",
                }
            ],
            "success": [],
            "targets": [],
            "unmatched_states": [
                {
                    "entity_id": "light.unmatched",
                    "last_changed": "0 seconds ago",
                    "name": "unmatched",
                    "state": "on",
                }
            ],
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
        description="test_description",
    )
    assert tool.description == "test_description"
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
            "test_assistant",
            "test_conversation_id",
            "test_device_id",
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
