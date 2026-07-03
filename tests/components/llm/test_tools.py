"""Tests for the LLM integration's own tools platform."""

from freezegun import freeze_time

from homeassistant.components import llm as llm_component
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


async def test_get_datetime_tool(hass: HomeAssistant) -> None:
    """Test the GetDateTime tool is always offered and works."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "llm", {})

    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context)
    tool = next((tool for tool in result.tools if tool.name == "GetDateTime"), None)
    assert tool is not None

    with freeze_time("2025-09-17 13:00:00-05:00"):
        response = await tool.async_call(
            hass, llm.ToolInput("GetDateTime", {}), llm_context
        )

    assert response["success"] is True
    assert set(response["result"]) == {"date", "time", "timezone", "weekday"}
