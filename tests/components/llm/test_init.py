"""Tests for the LLM integration."""

from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.llm import (
    LLMTools,
    async_get_tools,
    async_register_tool_provider,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType

from tests.common import mock_platform


class _StubTool(llm.Tool):
    """Minimal tool for registry tests."""

    def __init__(self, name: str) -> None:
        """Initialize the stub tool."""
        self.name = name
        self.description = f"{name} description"

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Return an empty result."""
        return {}


@pytest.fixture
def llm_context() -> llm.LLMContext:
    """Return an LLM context."""
    return llm.LLMContext(
        platform="test",
        context=None,
        language="*",
        assistant="conversation",
        device_id=None,
    )


async def test_setup(hass: HomeAssistant) -> None:
    """Test the integration sets up."""
    assert await async_setup_component(hass, "llm", {})


async def test_tool_platform_discovery(hass: HomeAssistant) -> None:
    """Test that an integration's llm tools platform is set up."""
    platform = Mock(async_setup_tools=AsyncMock())
    mock_platform(hass, "test.llm", platform)
    hass.config.components.add("test")

    assert await async_setup_component(hass, "llm", {})
    await hass.async_block_till_done()

    platform.async_setup_tools.assert_awaited_once_with(hass)


async def test_register_tool_provider(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test registering and unregistering a tool provider."""
    tool = _StubTool("my_tool")

    @callback
    def provider(_hass: HomeAssistant, _llm_context: llm.LLMContext) -> LLMTools:
        return LLMTools(tools=[tool], prompt="use my_tool wisely")

    unreg = async_register_tool_provider(hass, provider)

    result = async_get_tools(hass, llm_context)
    assert result.tools == [tool]
    assert result.prompt == "use my_tool wisely"

    unreg()
    result = async_get_tools(hass, llm_context)
    assert result.tools == []
    assert result.prompt is None


async def test_register_tool_provider_merges(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test that tools and prompts from multiple providers are merged."""
    tool_a = _StubTool("tool_a")
    tool_b = _StubTool("tool_b")

    @callback
    def provider_a(_hass: HomeAssistant, _llm_context: llm.LLMContext) -> LLMTools:
        return LLMTools(tools=[tool_a], prompt="prompt a")

    @callback
    def provider_b(_hass: HomeAssistant, _llm_context: llm.LLMContext) -> LLMTools:
        return LLMTools(tools=[tool_b], prompt="prompt b")

    async_register_tool_provider(hass, provider_a)
    async_register_tool_provider(hass, provider_b)

    result = async_get_tools(hass, llm_context)
    assert result.tools == [tool_a, tool_b]
    assert result.prompt == "prompt a\nprompt b"
