"""Tests for the script LLM tools platform."""

from unittest.mock import patch

import probatio
import pytest

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.script import llm as script_llm
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er, llm
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType

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
                "123456": {"description": 0, "sequence": []},
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


def _list_scripts_expected(last_triggered: str | None) -> list[JsonObjectType]:
    """Return the listed scripts of the fixture, sorted by name."""
    return [
        {
            "entity_id": "script.123456",
            "name": "123456",
            "state": "off",
            "last_triggered": None,
            "description": "0",
        },
        {
            "entity_id": ENTITY_ID,
            "name": "test script",
            "state": "off",
            "last_triggered": last_triggered,
            "description": "This is a test script",
        },
        {
            "entity_id": "script.unexposed_script",
            "name": "unexposed_script",
            "state": "off",
            "last_triggered": None,
        },
    ]


async def _list_scripts(
    hass: HomeAssistant, tool_args: JsonObjectType
) -> JsonObjectType:
    """Call the list scripts tool and return its result."""
    tool = script_llm.ListScriptsTool()
    result = await tool.async_call(
        hass, llm.ToolInput(tool.name, tool_args), _llm_context()
    )
    assert result.error is False
    return result.data


async def test_home_assistant_api_tools(hass: HomeAssistant) -> None:
    """Test the Home Assistant API gets the list tool, not the script tools."""
    tools = script_llm.async_get_tools(hass, _llm_context(), llm.LLM_API_HOME_ASSISTANT)
    assert tools is not None
    assert [tool.name for tool in tools.tools] == ["script__list_scripts"]


@pytest.mark.freeze_time("2026-11-24 12:00:00+00:00")
async def test_list_scripts(hass: HomeAssistant) -> None:
    """Test listing the scripts sorted by name."""
    await hass.services.async_call(
        "script", "turn_on", {"entity_id": ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()

    assert await _list_scripts(hass, {}) == {
        "scripts": _list_scripts_expected("2026-11-24T12:00:00+00:00"),
        "total": 3,
    }


async def test_list_scripts_pages(hass: HomeAssistant) -> None:
    """Test the next_offset points to the next page."""
    with patch("homeassistant.components.script.llm._LIMIT", 2):
        first = await _list_scripts(hass, {})
        second = await _list_scripts(hass, {"offset": first["next_offset"]})

    assert first == {
        "scripts": _list_scripts_expected(None)[:2],
        "total": 3,
        "next_offset": 2,
    }
    assert second == {"scripts": _list_scripts_expected(None)[2:], "total": 3}


@pytest.mark.parametrize("offset", [-1, "first"])
async def test_list_scripts_invalid_offset(hass: HomeAssistant, offset: object) -> None:
    """Test an invalid offset is rejected by the schema."""
    tool = script_llm.ListScriptsTool()
    with pytest.raises(probatio.Invalid):
        await tool.async_call(
            hass, llm.ToolInput(tool.name, {"offset": offset}), _llm_context()
        )
