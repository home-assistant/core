"""Tests for the humidifier LLM tools platform."""

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
    """Return the names of the tools offered by the humidifier platform."""
    result = await llm_component.async_get_tools(hass, _llm_context())
    return {tool.name for tool in result.tools}


async def test_humidifier_intent_tool_requires_exposed_entity(hass: HomeAssistant) -> None:
    """Test the intent tools are only exposed when a humidifier entity is exposed."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "humidifier", {})
    assert await async_setup_component(hass, "llm", {})
    await hass.async_block_till_done()

    assert "HassHumidifierMode" not in await _tool_names(hass)

    hass.states.async_set("humidifier.test", "on", {"friendly_name": "Test humidifier"})
    async_expose_entity(hass, "conversation", "humidifier.test", True)

    assert "HassHumidifierMode" in await _tool_names(hass)
