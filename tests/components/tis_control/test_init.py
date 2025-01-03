"""Test the TISControl integration."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.tis_control import async_setup_entry, async_unload_entry
from homeassistant.core import HomeAssistant

from .conftest import MockTISApi


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_setup_entry,
) -> None:
    """Test successful async_setup_entry."""
    with patch(
        "homeassistant.components.tis_control.TISApi",
        new=MockTISApi,
    ):
        # modify domain
        result = await async_setup_entry(hass, mock_setup_entry)
        assert result is True


@pytest.mark.asyncio
async def test_async_setup_entry_failure(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test async_setup_entry with connection failure."""
    with (
        patch.object(
            MockTISApi, "connect", side_effect=ConnectionError("Connection error")
        ),
        patch(
            "homeassistant.components.tis_control.TISApi",
            new=MockTISApi,
        ),
    ):
        result = await async_setup_entry(hass, mock_setup_entry)
        assert result is False


@pytest.mark.asyncio
async def test_async_unload_entry_success_with_tis_api(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test successful unload of entry with tis_api present."""
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        result = await async_unload_entry(hass, mock_setup_entry)
        assert result is True


@pytest.mark.asyncio
async def test_async_unload_entry_success_without_tis_api(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test successful unload of entry without tis_api present."""
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        result = await async_unload_entry(hass, mock_setup_entry)
        assert result is True


@pytest.mark.asyncio
async def test_async_unload_entry_failure(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test unsuccessful unload of entry."""
    entry = MagicMock()

    # Patch the async_unload_platforms method of hass.config_entries
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ) as mock_unload_platforms:
        result = await async_unload_entry(hass, entry)

        assert result is False
        mock_unload_platforms.assert_called_once()
