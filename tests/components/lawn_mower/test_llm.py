"""Tests for the lawn_mower LLM tools platform."""

import pytest

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.lawn_mower import llm as lawn_mower_llm
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

ENTITY_ID = "lawn_mower.test"
INTENTS = {"HassLawnMowerDock", "HassLawnMowerStartMowing"}


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations and expose a lawn_mower entity."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "lawn_mower", {})
    assert await async_setup_component(hass, "llm", {})
    hass.states.async_set(ENTITY_ID, "on", {"friendly_name": "Test lawn_mower"})
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
    """Return the names of the tools offered by the lawn_mower platform."""
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    return {tool.name for tool in result.tools}


async def test_intent_tool_exposed(hass: HomeAssistant) -> None:
    """Test the intent tool is offered for an exposed lawn_mower entity."""
    assert await _tool_names(hass) >= INTENTS


async def test_intent_tool_not_exposed(hass: HomeAssistant) -> None:
    """Test the intent tool is hidden when no lawn_mower entity is exposed."""
    async_expose_entity(hass, "conversation", ENTITY_ID, False)
    assert not INTENTS & await _tool_names(hass)
    assert lawn_mower_llm.async_get_tools(hass, _llm_context(), "assist") is None


async def test_no_tools_for_other_api(hass: HomeAssistant) -> None:
    """Test the platform returns None for an unsupported API."""
    assert lawn_mower_llm.async_get_tools(hass, _llm_context(), "other") is None
