"""Tests for the script LLM tools platform."""

import pytest

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.script import llm as script_llm
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
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


async def test_script_tool_only_exposed(hass: HomeAssistant) -> None:
    """Test only exposed scripts get a tool."""
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    names = [tool.name for tool in result.tools]
    assert "test_script" in names
    assert "unexposed_script" not in names


async def test_script_tool_not_exposed(hass: HomeAssistant) -> None:
    """Test no script tool is offered when the script is not exposed."""
    async_expose_entity(hass, "conversation", ENTITY_ID, False)
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    assert "test_script" not in [tool.name for tool in result.tools]
    assert script_llm.async_get_tools(hass, _llm_context(), "assist") is None


async def test_no_tools_for_other_api(hass: HomeAssistant) -> None:
    """Test the platform returns None for an unsupported API."""
    assert script_llm.async_get_tools(hass, _llm_context(), "other") is None


async def test_script_tool_call(hass: HomeAssistant) -> None:
    """Test calling the exposed script through its tool."""
    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context, "assist")
    tool = next(tool for tool in result.tools if tool.name == "test_script")

    response = await tool.async_call(
        hass, llm.ToolInput("test_script", {"beer": 1}), llm_context
    )
    assert response == {"success": True, "result": {"drinks": 2}}
