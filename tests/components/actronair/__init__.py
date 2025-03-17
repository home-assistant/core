"""Tests for the Actron Air integration setup."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.actronair import async_setup_entry, async_unload_entry
from homeassistant.components.actronair.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test successful setup of ActronAir integration."""
    mock_entry = mock_config_entry
    mock_entry.domain = DOMAIN

    with patch("custom_components.actronair.api.ActronAirApi") as mock_api:
        mock_api.return_value = AsyncMock()
        result = await async_setup_entry(hass, mock_entry)
        assert result is True


async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test unloading the ActronAir integration."""
    mock_entry = mock_config_entry
    result = await async_unload_entry(hass, mock_entry)
    assert result is True
