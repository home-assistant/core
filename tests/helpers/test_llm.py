"""Tests for the llm helpers."""

from unittest.mock import Mock, patch

import pytest
import voluptuous as vol

from homeassistant.core import Context, HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    floor_registry as fr,
    intent,
    llm,
)

from tests.common import MockConfigEntry


async def test_get_api_no_existing(hass: HomeAssistant) -> None:
    """Test getting an llm api where no config exists."""
    with pytest.raises(HomeAssistantError):
        llm.async_get_api(hass, "non-existing")


async def test_register_api(hass: HomeAssistant) -> None:
    """Test registering an llm api."""

    class MyAPI(llm.API):
        async def async_get_api_prompt(self, tool_input: llm.ToolInput) -> str:
            """Return a prompt for the tool."""
            return ""

        def async_get_tools(self) -> list[llm.Tool]:
            """Return a list of tools."""
            return []

    api = MyAPI(hass=hass, id="test", name="Test")
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


async def test_assist_api_prompt(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test prompt for the assist API."""
    context = Context()
    tool_input = llm.ToolInput(
        tool_name=None,
        tool_args=None,
        platform="test_platform",
        context=context,
        user_prompt="test_text",
        language="*",
        assistant="test_assistant",
        device_id="test_device",
    )
    api = llm.async_get_api(hass, "assist")
    prompt = await api.async_get_api_prompt(tool_input)
    assert (
        prompt
        == "Call the intent tools to control Home Assistant. Just pass the name to the intent."
    )

    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)
    tool_input.device_id = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "1234")},
        name="Test Device",
        manufacturer="Test Manufacturer",
        model="Test Model",
        suggested_area="Test Area",
    ).id
    prompt = await api.async_get_api_prompt(tool_input)
    assert (
        prompt
        == "Call the intent tools to control Home Assistant. Just pass the name to the intent. You are in Test Area."
    )

    floor = floor_registry.async_create("second floor")
    area = area_registry.async_get_area_by_name("Test Area")
    area_registry.async_update(area.id, floor_id=floor.floor_id)
    prompt = await api.async_get_api_prompt(tool_input)
    assert (
        prompt
        == "Call the intent tools to control Home Assistant. Just pass the name to the intent. You are in Test Area (second floor)."
    )

    context.user_id = "12345"
    mock_user = Mock()
    mock_user.id = "12345"
    mock_user.name = "Test User"
    with patch("homeassistant.auth.AuthManager.async_get_user", return_value=mock_user):
        prompt = await api.async_get_api_prompt(tool_input)
    assert (
        prompt
        == "Call the intent tools to control Home Assistant. Just pass the name to the intent. You are in Test Area (second floor). The user name is Test User."
    )
