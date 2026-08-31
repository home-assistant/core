"""Tests for the assist_satellite LLM tools platform."""

import pytest

from homeassistant.components import llm as llm_component
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def init_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations; assist_satellite registers the broadcast intent."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "llm", {})
    assert await async_setup_component(hass, "assist_satellite", {})


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
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    assert "HassBroadcast" in [tool.name for tool in result.tools]
