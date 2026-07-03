"""Tests for the climate LLM tools platform."""

import pytest

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations for the climate LLM tools platform."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "climate", {})
    assert await async_setup_component(hass, "llm", {})
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
    """Return the names of the tools offered by the climate platform."""
    result = await llm_component.async_get_tools(hass, _llm_context())
    return {tool.name for tool in result.tools}


async def test_climate_intent_tool_requires_exposed_entity(hass: HomeAssistant) -> None:
    """Test the intent tools are only exposed when a climate entity is exposed."""
    assert "HassClimateSetTemperature" not in await _tool_names(hass)

    hass.states.async_set("climate.test", "on", {"friendly_name": "Test climate"})
    async_expose_entity(hass, "conversation", "climate.test", True)

    assert "HassClimateSetTemperature" in await _tool_names(hass)
