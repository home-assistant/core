"""Tests for the homeassistant LLM tools platform."""

import pytest

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

ENTITY_ID = "light.kitchen"


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations and expose an entity."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "llm", {})
    hass.states.async_set(ENTITY_ID, "on", {"friendly_name": "Kitchen Light"})
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


async def test_live_context_always_offered(hass: HomeAssistant) -> None:
    """Test GetLiveContext is offered even when nothing is exposed."""
    async_expose_entity(hass, "conversation", ENTITY_ID, False)
    result = await llm_component.async_get_tools(hass, _llm_context())
    assert [tool.name for tool in result.tools] == ["GetLiveContext"]


async def test_get_live_context_tool(hass: HomeAssistant) -> None:
    """Test GetLiveContext returns exposed entity state."""
    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context)
    tool = next((tool for tool in result.tools if tool.name == "GetLiveContext"), None)
    assert tool is not None

    response = await tool.async_call(
        hass, llm.ToolInput("GetLiveContext", {}), llm_context
    )
    assert response["success"] is True
    assert "Kitchen Light" in response["result"]
