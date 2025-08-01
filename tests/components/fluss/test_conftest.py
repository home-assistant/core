"""Shared test fixtures for Fluss+ integration."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
async def mock_hass():
    """Mock Hass Environment."""
    hass = AsyncMock(spec=HomeAssistant)
    hass.config_entries = AsyncMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock()
    hass.data = {}
    return hass
