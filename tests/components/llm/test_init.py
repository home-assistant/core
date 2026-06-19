"""Tests for the LLM integration."""

from unittest.mock import AsyncMock, Mock

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import mock_platform


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
