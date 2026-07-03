"""Tests for the vacuum LLM tools platform."""

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


async def _tool_names(hass: HomeAssistant) -> set[str]:
    """Return the names of the tools offered by the vacuum platform."""
    result = await llm_component.async_get_tools(hass, _llm_context())
    return {tool.name for tool in result.tools}


async def test_vacuum_intent_tool_requires_exposed_entity(hass: HomeAssistant) -> None:
    """Test the intent tools are only exposed when a vacuum entity is exposed."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "vacuum", {})
    assert await async_setup_component(hass, "llm", {})
    await hass.async_block_till_done()

    assert "HassVacuumStart" not in await _tool_names(hass)

    hass.states.async_set("vacuum.test", "on", {"friendly_name": "Test vacuum"})
    async_expose_entity(hass, "conversation", "vacuum.test", True)

    assert "HassVacuumStart" in await _tool_names(hass)
