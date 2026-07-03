"""Tests for the LLM integration's own tools platform."""

from freezegun import freeze_time
import pytest

from homeassistant.components import llm as llm_component
from homeassistant.components.llm import llm as llm_platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations for the llm tools platform."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "llm", {})
    await hass.config.async_set_time_zone("UTC")
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


async def test_get_datetime_tool(hass: HomeAssistant) -> None:
    """Test the GetDateTime tool is always offered and returns the current time."""
    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context, "assist")
    tool = next((tool for tool in result.tools if tool.name == "GetDateTime"), None)
    assert tool is not None

    with freeze_time("2025-09-17 13:00:00"):
        response = await tool.async_call(
            hass, llm.ToolInput("GetDateTime", {}), llm_context
        )

    assert response == {
        "success": True,
        "result": {
            "date": "2025-09-17",
            "time": "13:00:00",
            "timezone": "UTC",
            "weekday": "Wednesday",
        },
    }


async def test_no_tools_for_other_api(hass: HomeAssistant) -> None:
    """Test the platform returns None for an unsupported API."""
    assert llm_platform.async_get_tools(hass, _llm_context(), "other") is None
