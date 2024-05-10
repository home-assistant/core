"""Tests for the llm helpers."""

from unittest.mock import AsyncMock

import pytest
import voluptuous as vol

from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm


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
    def test_function(
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
    assert tool.name == "test_function"
    assert tool.description == "Test tool description."

    schema = {
        vol.Required("required_arg"): int,
        vol.Optional("optional_arg", default=9.6): vol.Any(float, str),
    }
    tool_schema = tool.parameters.schema
    assert isinstance(tool_schema[vol.Optional("optional_arg", default=9.6)], vol.Any)
    assert tool_schema[vol.Optional("optional_arg", default=9.6)].validators == (
        float,
        str,
    )
    schema[vol.Optional("optional_arg", default=9.6)] = tool_schema[
        vol.Optional("optional_arg", default=9.6)
    ]
    assert tool_schema == schema

    test_context = Context()
    tool_input = llm.ToolInput(
        tool_name="test_function",
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

    llm.async_remove_tool(hass, "test_function")

    assert list(llm.async_get_tools(hass)) == []


async def test_async_function_tool(hass: HomeAssistant) -> None:
    """Test function tools with async function."""
    call = {}

    @llm.llm_tool(hass)
    async def async_test_async_function(
        hass: HomeAssistant,
        platform: str,
        context: Context,
        required_arg: int | dict[str, int],
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
    assert tool.name == "test_async_function"
    assert tool.description == "Test tool description."

    schema = {
        vol.Required("required_arg"): vol.Any(int, {str: int}),
        vol.Optional("optional_arg"): vol.Maybe(float),
    }
    tool_schema = tool.parameters.schema

    assert isinstance(tool_schema[vol.Optional("optional_arg")], vol.Any)
    assert tool_schema[vol.Optional("optional_arg")].validators == (None, float)
    schema[vol.Optional("optional_arg")] = tool_schema[vol.Optional("optional_arg")]

    assert isinstance(tool_schema[vol.Required("required_arg")], vol.Any)
    assert tool_schema[vol.Required("required_arg")].validators == (int, {str: int})
    schema[vol.Required("required_arg")] = tool_schema[vol.Required("required_arg")]

    assert tool_schema == schema

    test_context = Context()
    tool_input = llm.ToolInput(
        tool_name="test_async_function",
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

    llm.async_remove_tool(hass, async_test_async_function)

    assert list(llm.async_get_tools(hass)) == []
