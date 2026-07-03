"""Tests for the intent LLM tools platform (generic intents)."""

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component


def _llm_context(device_id: str | None = None) -> llm.LLMContext:
    """Return an LLM context for the conversation assistant."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=device_id,
    )


async def _setup(hass: HomeAssistant) -> None:
    """Set up the homeassistant, intent and llm integrations."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "llm", {})
    await hass.async_block_till_done()


async def _tool_names(hass: HomeAssistant) -> set[str]:
    """Return the names of the tools offered by the intent platform."""
    result = await llm_component.async_get_tools(hass, _llm_context())
    return {tool.name for tool in result.tools}


async def test_generic_intents_exposed(hass: HomeAssistant) -> None:
    """Test the always-on generic intents are exposed."""
    await _setup(hass)
    names = await _tool_names(hass)
    assert "HassTurnOn" in names
    assert "HassTurnOff" in names


async def test_timer_intents_require_timer_device(hass: HomeAssistant) -> None:
    """Test timer intents are not exposed without a timer-capable device."""
    await _setup(hass)
    assert "HassStartTimer" not in await _tool_names(hass)


async def test_set_position_requires_exposed_cover(hass: HomeAssistant) -> None:
    """Test HassSetPosition is only exposed when a cover/valve is exposed."""
    await _setup(hass)
    assert "HassSetPosition" not in await _tool_names(hass)

    hass.states.async_set("cover.test", "open", {"friendly_name": "Test Cover"})
    async_expose_entity(hass, "conversation", "cover.test", True)

    assert "HassSetPosition" in await _tool_names(hass)
