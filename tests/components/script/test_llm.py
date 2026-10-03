"""Tests for the script LLM tools platform."""

from unittest.mock import patch

import pytest

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.script import ScriptConfig, llm as script_llm
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er, llm
from homeassistant.setup import async_setup_component

ENTITY_ID = "script.test_script"


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations and expose a script."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "llm", {})
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test_script": {
                    "alias": "test script",
                    "description": "This is a test script",
                    "sequence": [
                        {"variables": {"result": {"drinks": 2}}},
                        {"stop": True, "response_variable": "result"},
                    ],
                    "fields": {
                        "beer": {"description": "Number of beers", "required": True},
                    },
                },
                "unexposed_script": {"sequence": []},
                "123456": {"sequence": []},
            }
        },
    )
    async_expose_entity(hass, "conversation", ENTITY_ID, True)
    await hass.async_block_till_done()


def _llm_context() -> llm.LLMContext:
    """Return an LLM context for the conversation assistant."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=None,
    )


async def test_script_tool_title(hass: HomeAssistant) -> None:
    """Test the script tool is titled with the name the user gave the script."""
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    tool = next(tool for tool in result.tools if tool.name == "script__test_script")
    assert tool.title == "test script"
    assert tool.integration == "script"


async def test_script_tool_only_exposed(hass: HomeAssistant) -> None:
    """Test only exposed scripts get a tool."""
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    names = [tool.name for tool in result.tools]
    assert "script__test_script" in names
    assert "unexposed_script" not in names


async def test_script_tool_not_exposed(hass: HomeAssistant) -> None:
    """Test no script tool is offered when the script is not exposed."""
    async_expose_entity(hass, "conversation", ENTITY_ID, False)
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    assert "script__test_script" not in [tool.name for tool in result.tools]
    assert script_llm.async_get_tools(hass, _llm_context(), "assist") is None


async def test_no_tools_for_other_api(hass: HomeAssistant) -> None:
    """Test the platform returns None for an unsupported API."""
    assert script_llm.async_get_tools(hass, _llm_context(), "other") is None


async def test_script_tool_call(hass: HomeAssistant) -> None:
    """Test calling the exposed script through its tool."""
    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context, "assist")
    tool = next(tool for tool in result.tools if tool.name == "script__test_script")

    response = await tool.async_call(
        hass, llm.ToolInput("script__test_script", {"beer": 1}), llm_context
    )
    assert response == llm.ToolResult(data={"result": {"drinks": 2}})


async def test_script_tool_forwards_device_id(hass: HomeAssistant) -> None:
    """Test that ScriptTool forwards the calling device_id to the script."""
    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context, "assist")
    tool = next(tool for tool in result.tools if tool.name == "script__test_script")

    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        side_effect=hass.services.async_call,
    ) as mock_service_call:
        await tool.async_call(
            hass, llm.ToolInput("script__test_script", {"beer": 1}), llm_context
        )

    mock_service_call.assert_awaited_once_with(
        "script",
        "test_script",
        {"beer": 1},
        context=llm_context.context,
        blocking=True,
        return_response=True,
    )

    llm_context.device_id = "abc123"

    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        side_effect=hass.services.async_call,
    ) as mock_service_call:
        await tool.async_call(
            hass, llm.ToolInput("script__test_script", {"beer": 1}), llm_context
        )

    mock_service_call.assert_awaited_once_with(
        "script",
        "test_script",
        {"beer": 1, "device_id": "abc123"},
        context=llm_context.context,
        blocking=True,
        return_response=True,
    )

    # The script does not declare a device_id field, so an LLM-supplied
    # value for it is not trusted over the real calling device_id.
    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        side_effect=hass.services.async_call,
    ) as mock_service_call:
        await tool.async_call(
            hass,
            llm.ToolInput("script__test_script", {"beer": 1, "device_id": "spoofed"}),
            llm_context,
        )

    mock_service_call.assert_awaited_once_with(
        "script",
        "test_script",
        {"beer": 1, "device_id": "abc123"},
        context=llm_context.context,
        blocking=True,
        return_response=True,
    )


async def test_script_tool_does_not_overwrite_declared_device_id_field(
    hass: HomeAssistant,
) -> None:
    """Test that a script-declared device_id field is not overwritten."""
    config = {
        "script": {
            "test_script": ScriptConfig(
                {
                    "description": "This is a test script",
                    "sequence": [],
                    "mode": "single",
                    "max": 2,
                    "max_exceeded": "WARNING",
                    "trace": {"stored_traces": 5},
                    "fields": {"device_id": {"selector": {"text": {}}}},
                }
            )
        }
    }
    with patch(
        "homeassistant.helpers.entity_component.EntityComponent.async_prepare_reload",
        return_value=config,
    ):
        await hass.services.async_call("script", "reload", blocking=True)

    llm_context = _llm_context()
    llm_context.device_id = "abc123"
    result = await llm_component.async_get_tools(hass, llm_context, "assist")
    tool = next(tool for tool in result.tools if tool.name == "script__test_script")

    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        side_effect=hass.services.async_call,
    ) as mock_service_call:
        await tool.async_call(
            hass,
            llm.ToolInput("script__test_script", {"device_id": "living_room_tablet"}),
            llm_context,
        )

    mock_service_call.assert_awaited_once_with(
        "script",
        "test_script",
        {"device_id": "living_room_tablet"},
        context=llm_context.context,
        blocking=True,
        return_response=True,
    )


async def test_script_tool_name_not_started_with_digit(hass: HomeAssistant) -> None:
    """Test a script whose id starts with a digit gets a valid tool name."""
    async_expose_entity(hass, "conversation", "script.123456", True)
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    assert "script__123456" in [tool.name for tool in result.tools]


async def test_script_tool_description_includes_aliases(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the script tool description is extended with the entity aliases."""
    entity_registry.async_update_entity(ENTITY_ID, aliases=["barkeep", "pour a drink"])
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    tool = next(tool for tool in result.tools if tool.name == "script__test_script")
    assert tool.description == (
        "This is a test script. Aliases: ['barkeep', 'pour a drink']"
    )
