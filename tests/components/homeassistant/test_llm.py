"""Tests for the homeassistant LLM tools platform."""

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


async def test_no_live_context_without_exposed_entities(hass: HomeAssistant) -> None:
    """Test GetLiveContext is not offered when nothing is exposed."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "llm", {})

    result = await llm_component.async_get_tools(hass, _llm_context())
    assert [tool.name for tool in result.tools] == []


async def test_get_live_context_tool(hass: HomeAssistant) -> None:
    """Test GetLiveContext is offered and returns exposed entity state."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "llm", {})
    hass.states.async_set("light.kitchen", "on", {"friendly_name": "Kitchen Light"})
    async_expose_entity(hass, "conversation", "light.kitchen", True)

    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context)
    tool = next((tool for tool in result.tools if tool.name == "GetLiveContext"), None)
    assert tool is not None

    response = await tool.async_call(
        hass, llm.ToolInput("GetLiveContext", {}), llm_context
    )
    assert response["success"] is True
    assert "Kitchen Light" in response["result"]
