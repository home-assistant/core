"""Tests for the light LLM tools platform."""

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
    """Return the names of the tools offered by the light platform."""
    result = await llm_component.async_get_tools(hass, _llm_context())
    return {tool.name for tool in result.tools}


async def test_light_intent_tool_requires_exposed_entity(hass: HomeAssistant) -> None:
    """Test HassLightSet is only exposed when a light is exposed."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "light", {})
    assert await async_setup_component(hass, "llm", {})

    assert "HassLightSet" not in await _tool_names(hass)

    hass.states.async_set("light.kitchen", "on", {"friendly_name": "Kitchen Light"})
    async_expose_entity(hass, "conversation", "light.kitchen", True)

    assert "HassLightSet" in await _tool_names(hass)
