"""Tests for Vanderbilt SPC component."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_valid_device_config(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test valid device config."""
    config = {"spc": {"api_url": "http://localhost/", "ws_url": "ws://localhost/"}}

    assert await async_setup_component(hass, "spc", config) is True


async def test_invalid_device_config(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test valid device config."""
    config = {"spc": {"api_url": "http://localhost/"}}

    assert await async_setup_component(hass, "spc", config) is False
