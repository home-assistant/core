"""Tests for the light LLM tools platform."""

import pytest

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

ENTITY_ID = "light.test"


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations and expose a light entity."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "light", {})
    assert await async_setup_component(hass, "llm", {})
    hass.states.async_set(ENTITY_ID, "on", {"friendly_name": "Test light"})
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


async def _tool_names(hass: HomeAssistant) -> set[str]:
    """Return the names of the tools offered by the light platform."""
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    return {tool.name for tool in result.tools}


async def test_intent_tool_exposed(hass: HomeAssistant) -> None:
    """Test the intent tool is offered for an exposed light entity."""
    assert "HassLightSet" in await _tool_names(hass)


async def test_intent_tool_not_exposed(hass: HomeAssistant) -> None:
    """Test the intent tool is hidden when no light entity is exposed."""
    async_expose_entity(hass, "conversation", ENTITY_ID, False)
    assert "HassLightSet" not in await _tool_names(hass)
