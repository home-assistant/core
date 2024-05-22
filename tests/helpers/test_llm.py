"""Tests for the llm helpers."""

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.core import Context, HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, intent, llm


async def test_get_api_no_existing(hass: HomeAssistant) -> None:
    """Test getting an llm api where no config exists."""
    with pytest.raises(HomeAssistantError):
        llm.async_get_api(hass, "non-existing")


async def test_register_api(hass: HomeAssistant) -> None:
    """Test registering an llm api."""

    class MyAPI(llm.API):
        def async_get_tools(self) -> list[llm.Tool]:
            """Return a list of tools."""
            return []

    api = MyAPI(hass=hass, id="test", name="Test", prompt_template="")
    llm.async_register_api(hass, api)

    assert llm.async_get_api(hass, "test") is api
    assert api in llm.async_get_apis(hass)

    with pytest.raises(HomeAssistantError):
        llm.async_register_api(hass, api)


async def test_call_tool_no_existing(hass: HomeAssistant) -> None:
    """Test calling an llm tool where no config exists."""
    with pytest.raises(HomeAssistantError):
        await llm.async_get_api(hass, "intent").async_call_tool(
            llm.ToolInput(
                "test_tool",
                {},
                "test_platform",
                None,
                None,
                None,
                None,
                None,
            ),
        )


async def test_assist_api(hass: HomeAssistant) -> None:
    """Test Assist API."""
    schema = {
        vol.Optional("area"): cv.string,
        vol.Optional("floor"): cv.string,
    }

    class MyIntentHandler(intent.IntentHandler):
        intent_type = "test_intent"
        slot_schema = schema

    intent_handler = MyIntentHandler()

    intent.async_register(hass, intent_handler)

    assert len(llm.async_get_apis(hass)) == 1
    api = llm.async_get_api(hass, "assist")
    tools = api.async_get_tools()
    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "test_intent"
    assert tool.description == "Execute Home Assistant test_intent intent"
    assert tool.parameters == vol.Schema(intent_handler.slot_schema)
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
        assistant="test_assistant",
        device_id="test_device",
    )

    with patch(
        "homeassistant.helpers.intent.async_handle", return_value=intent_response
    ) as mock_intent_handle:
        response = await api.async_call_tool(tool_input)

    mock_intent_handle.assert_awaited_once_with(
        hass,
        "test_platform",
        "test_intent",
        {
            "area": {"value": "kitchen"},
            "floor": {"value": "ground_floor"},
        },
        "test_text",
        test_context,
        "*",
        "test_assistant",
        "test_device",
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


async def test_assist_api_description(hass: HomeAssistant) -> None:
    """Test intent description with Assist API."""

    class MyIntentHandler(intent.IntentHandler):
        intent_type = "test_intent"
        description = "my intent handler"

    intent.async_register(hass, MyIntentHandler())

    assert len(llm.async_get_apis(hass)) == 1
    api = llm.async_get_api(hass, "assist")
    tools = api.async_get_tools()
    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "test_intent"
    assert tool.description == "my intent handler"
