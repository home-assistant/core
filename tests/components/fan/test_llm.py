"""Tests for the fan LLM tools platform."""

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
    """Return the names of the tools offered by the fan platform."""
    result = await llm_component.async_get_tools(hass, _llm_context())
    return {tool.name for tool in result.tools}


async def test_fan_intent_tool_requires_exposed_entity(hass: HomeAssistant) -> None:
    """Test the intent tools are only exposed when a fan entity is exposed."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "fan", {})
    assert await async_setup_component(hass, "llm", {})
    await hass.async_block_till_done()

    assert "HassFanSetSpeed" not in await _tool_names(hass)

    hass.states.async_set("fan.test", "on", {"friendly_name": "Test fan"})
    async_expose_entity(hass, "conversation", "fan.test", True)

    assert "HassFanSetSpeed" in await _tool_names(hass)
