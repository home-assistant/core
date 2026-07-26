"""Tests for the intent LLM tools platform (generic intents)."""

import pytest

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.intent import llm as intent_llm
from homeassistant.components.intent.timers import async_register_timer_handler
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

COVER_ENTITY_ID = "cover.test"


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations and expose a cover."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "llm", {})
    hass.states.async_set(COVER_ENTITY_ID, "open", {"friendly_name": "Test Cover"})
    async_expose_entity(hass, "conversation", COVER_ENTITY_ID, True)
    await hass.async_block_till_done()


def _llm_context(device_id: str | None = None) -> llm.LLMContext:
    """Return an LLM context for the conversation assistant."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=device_id,
    )


async def _tool_names(hass: HomeAssistant) -> set[str]:
    """Return the names of the tools offered by the intent platform."""
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    return {tool.name for tool in result.tools}


async def test_generic_intents_exposed(hass: HomeAssistant) -> None:
    """Test the always-on generic intents are exposed."""
    names = await _tool_names(hass)
    assert "HassTurnOn" in names
    assert "HassTurnOff" in names


async def test_timer_intents_require_timer_device(hass: HomeAssistant) -> None:
    """Test timer intents are not exposed without a timer-capable device."""
    assert "HassStartTimer" not in await _tool_names(hass)


async def test_timer_intents_offered_for_timer_device(hass: HomeAssistant) -> None:
    """Test timer intents are exposed for a timer-capable device."""

    @callback
    def handle_timer(*args: object) -> None:
        pass

    async_register_timer_handler(hass, "test_device", handle_timer)

    result = await llm_component.async_get_tools(
        hass, _llm_context(device_id="test_device"), "assist"
    )
    names = {tool.name for tool in result.tools}
    assert "HassStartTimer" in names
    assert "HassTimerStatus" in names


async def test_set_position_requires_exposed_cover(hass: HomeAssistant) -> None:
    """Test HassSetPosition is only exposed when a cover/valve is exposed."""
    assert "HassSetPosition" in await _tool_names(hass)

    async_expose_entity(hass, "conversation", COVER_ENTITY_ID, False)
    assert "HassSetPosition" not in await _tool_names(hass)


async def test_prompt_includes_device_control(hass: HomeAssistant) -> None:
    """Test the platform contributes device-control guidance when exposed."""
    result = intent_llm.async_get_tools(hass, _llm_context(), "assist")
    assert result is not None
    assert result.prompt is not None
    assert intent_llm.DEVICE_CONTROL_TOOL_USAGE_PROMPT in result.prompt
    assert "This device is not able to start timers." in result.prompt


async def test_no_prompt_without_exposed_entities(hass: HomeAssistant) -> None:
    """Test the platform contributes no prompt when nothing is exposed."""
    async_expose_entity(hass, "conversation", COVER_ENTITY_ID, False)
    result = intent_llm.async_get_tools(hass, _llm_context(), "assist")
    assert result is not None
    assert result.prompt is None


async def test_no_tools_for_other_api(hass: HomeAssistant) -> None:
    """Test the platform returns None for an unsupported API."""
    assert intent_llm.async_get_tools(hass, _llm_context(), "other") is None
