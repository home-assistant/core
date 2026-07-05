"""Tests for the assist_satellite LLM tools platform."""

from homeassistant.components.assist_satellite import llm as assist_satellite_llm
from homeassistant.components.assist_satellite.intent import BroadcastIntentHandler
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent, llm


def _llm_context() -> llm.LLMContext:
    """Return an LLM context for the conversation assistant."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=None,
    )


async def test_broadcast_tool_offered(hass: HomeAssistant) -> None:
    """Test the broadcast intent is exposed as an LLM tool."""
    intent.async_register(hass, BroadcastIntentHandler())
    result = assist_satellite_llm.async_get_tools(hass, _llm_context(), "assist")
    assert result is not None
    assert [tool.name for tool in result.tools] == ["HassBroadcast"]


async def test_no_tool_without_intent(hass: HomeAssistant) -> None:
    """Test no tool is offered when the broadcast intent is not registered."""
    assert assist_satellite_llm.async_get_tools(hass, _llm_context(), "assist") is None


async def test_no_tools_for_other_api(hass: HomeAssistant) -> None:
    """Test the platform returns None for an unsupported API."""
    intent.async_register(hass, BroadcastIntentHandler())
    assert assist_satellite_llm.async_get_tools(hass, _llm_context(), "other") is None
