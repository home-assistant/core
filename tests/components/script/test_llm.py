"""Tests for the script LLM tools platform."""

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component


def _llm_context() -> llm.LLMContext:
    """Return an LLM context for the conversation assistant."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=None,
    )


async def _setup(hass: HomeAssistant) -> None:
    """Set up the integrations and an exposed script."""
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


async def test_script_tool_only_exposed(hass: HomeAssistant) -> None:
    """Test only exposed scripts get a tool."""
    await _setup(hass)
    async_expose_entity(hass, "conversation", "script.test_script", True)

    result = await llm_component.async_get_tools(hass, _llm_context())
    assert [tool.name for tool in result.tools] == ["test_script"]


async def test_script_tool_call(hass: HomeAssistant) -> None:
    """Test calling the exposed script through its tool."""
    await _setup(hass)
    async_expose_entity(hass, "conversation", "script.test_script", True)

    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context)
    tool = next(tool for tool in result.tools if tool.name == "test_script")

    response = await tool.async_call(
        hass, llm.ToolInput("test_script", {"beer": 1}), llm_context
    )
    assert response == {"success": True, "result": {"drinks": 2}}
