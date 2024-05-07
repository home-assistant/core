"""Tests for the llm helpers."""

from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
from voluptuous_openapi import UNSUPPORTED

from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, llm
from homeassistant.util.color import color_name_to_rgb


def test_async_register(hass: HomeAssistant) -> None:
    """Test registering an llm tool and verifying it is stored correctly."""
    tool = llm.Tool()
    tool.name = "test_tool"
    tool.description = "test_description"

    llm.async_register_tool(hass, tool)

    assert hass.data[llm.DATA_KEY]["test_tool"] == tool
    assert list(llm.async_get_tools(hass)) == [tool]


def test_async_register_overwrite(hass: HomeAssistant) -> None:
    """Test registering multiple tools with the same name, ensuring the second time an exception is raised."""
    tool1 = llm.Tool()
    tool1.name = "test_tool"
    tool1.description = "test_tool_1"
    tool2 = llm.Tool()
    tool2.name = "test_tool"
    tool2.description = "test_tool_2"

    llm.async_register_tool(hass, tool1)
    with pytest.raises(HomeAssistantError):
        llm.async_register_tool(hass, tool2)

    assert hass.data[llm.DATA_KEY]["test_tool"] == tool1
    assert list(llm.async_get_tools(hass)) == [tool1]


def test_async_remove(hass: HomeAssistant) -> None:
    """Test removing a tool and verifying it is no longer present in the Home Assistant data."""
    tool = llm.Tool()
    tool.name = "test_tool"
    tool.description = "test_description"

    llm.async_register_tool(hass, tool)
    llm.async_remove_tool(hass, tool)

    assert "test_tool" not in hass.data[llm.DATA_KEY]
    assert list(llm.async_get_tools(hass)) == []


def test_async_remove_no_existing_entry(hass: HomeAssistant) -> None:
    """Test the removal of a non-existing tool from Home Assistant's data."""
    tool = llm.Tool()
    tool.name = "test_tool"
    tool.description = "test_description"
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
    tool = llm.Tool()
    tool.name = "test_tool"
    tool.description = "test_description"
    tool.parameters = vol.Schema({"test_arg": str})
    tool.async_call = AsyncMock(return_value={"result": "test_response"})

    llm.async_register_tool(hass, tool)
    test_context = Context()

    tool_input = llm.ToolInput(
        tool_name="test_tool",
        tool_args={"test_arg": "test_value"},
        platform="test_platform",
        context=test_context,
        user_prompt="test_text",
        language="en",
        agent_id="test_agent",
        conversation_id="test_conversation_id",
        device_id="test_device_id",
        assistant="test_assistant",
    )

    response = await llm.async_call_tool(hass, tool_input)

    tool.async_call.assert_awaited_once_with(hass, tool_input)
    assert response == {"result": "test_response"}


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


async def test_function_tool(hass: HomeAssistant) -> None:
    """Test function tools."""
    call = {}

    @llm.llm_tool(hass)
    def test_async_function_tool(
        hass: HomeAssistant,
        platform: str,
        context: Context,
        required_arg: int,
        optional_arg: float | str = 9.6,
    ):
        """Test tool description."""
        call["hass"] = hass
        call["platform"] = platform
        call["context"] = context
        call["required_arg"] = required_arg
        call["optional_arg"] = optional_arg
        return {"result": "test_response"}

    tool = list(llm.async_get_tools(hass))[0]
    assert tool.specification == {
        "name": "test_async_function_tool",
        "description": "Test tool description.",
        "parameters": {
            "type": "object",
            "properties": {
                "optional_arg": {
                    "anyOf": [
                        {
                            "type": "number",
                        },
                        {
                            "type": "string",
                        },
                    ],
                    "default": 9.6,
                },
                "required_arg": {
                    "type": "integer",
                },
            },
            "required": ["required_arg"],
        },
    }

    test_context = Context()
    tool_input = llm.ToolInput(
        tool_name="test_async_function_tool",
        tool_args={"required_arg": 4},
        platform="test_platform",
        context=test_context,
        user_prompt="test_text",
        language="en",
        agent_id="test_agent",
        conversation_id="test_conversation_id",
        device_id="test_device_id",
        assistant="test_assistant",
    )

    response = await llm.async_call_tool(hass, tool_input)

    assert response == {"result": "test_response"}
    assert call == {
        "context": test_context,
        "hass": hass,
        "optional_arg": 9.6,
        "platform": "test_platform",
        "required_arg": 4,
    }

    llm.async_remove_tool(hass, "test_async_function_tool")

    assert list(llm.async_get_tools(hass)) == []


async def test_async_function_tool(hass: HomeAssistant) -> None:
    """Test function tools with async function."""
    call = {}

    @llm.llm_tool(hass)
    async def async_test_async_function_tool(
        hass: HomeAssistant,
        platform: str,
        context: Context,
        required_arg: int,
        optional_arg: None | float = None,
    ):
        """Test tool description."""
        call["hass"] = hass
        call["platform"] = platform
        call["context"] = context
        call["required_arg"] = required_arg
        call["optional_arg"] = optional_arg
        return {"result": "test_response"}

    tool = list(llm.async_get_tools(hass))[0]
    assert tool.specification == {
        "name": "test_async_function_tool",
        "description": "Test tool description.",
        "parameters": {
            "type": "object",
            "properties": {
                "optional_arg": {
                    "type": "number",
                    "nullable": True,
                    "default": None,
                },
                "required_arg": {
                    "type": "integer",
                },
            },
            "required": ["required_arg"],
        },
    }

    test_context = Context()
    tool_input = llm.ToolInput(
        tool_name="test_async_function_tool",
        tool_args={"required_arg": 4},
        platform="test_platform",
        context=test_context,
        user_prompt="test_text",
        language="en",
        agent_id="test_agent",
        conversation_id="test_conversation_id",
        device_id="test_device_id",
        assistant="test_assistant",
    )

    response = await llm.async_call_tool(hass, tool_input)

    assert response == {"result": "test_response"}
    assert call == {
        "context": test_context,
        "hass": hass,
        "optional_arg": None,
        "platform": "test_platform",
        "required_arg": 4,
    }

    llm.async_remove_tool(hass, async_test_async_function_tool)

    assert list(llm.async_get_tools(hass)) == []


def test_custom_serializer() -> None:
    """Test custom serializer."""
    tool = llm.Tool()
    assert tool.custom_serializer(cv.string) == {"type": "string"}
    assert tool.custom_serializer(cv.boolean) == {"type": "boolean"}
    assert tool.custom_serializer(color_name_to_rgb) == {"type": "string"}
    assert tool.custom_serializer(cv.multi_select(["alpha", "beta"])) == {
        "enum": ["alpha", "beta"]
    }
    assert tool.custom_serializer(lambda x: x) == {}
    assert tool.custom_serializer("unsupported") == UNSUPPORTED
