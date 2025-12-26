"""Tests for the TIS Control integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.tis_control import async_setup_entry, async_unload_entry
from homeassistant.components.tis_control.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.tis_control.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        mock_setup_entry.data = {"port": "6000"}
        mock_setup_entry.domain = DOMAIN
        mock_setup_entry.entry_id = "1234"
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="CN11A1A00001",
        domain=DOMAIN,
        data={
            "port": "6000",
        },
        unique_id="CN11A1A00001",
    )


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


# setup entry
@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test successful setup of entry."""
    with (
        patch("homeassistant.components.tis_control.TISApi.connect"),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
    ):
        result = await async_setup_entry(hass, mock_config_entry)
        assert result


@pytest.mark.asyncio
async def test_async_setup_entry_failure(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test unsuccessful setup of entry."""
    with (
        patch(
            "homeassistant.components.tis_control.TISApi.connect",
            side_effect=ConnectionError("Test error"),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
        # Use pytest.raises to catch the expected exception
        pytest.raises(ConfigEntryNotReady),
    ):
        # This call will now raise the exception and be caught by pytest.raises
        await async_setup_entry(hass, mock_config_entry)

    # This assertion is still valid and important.
    # It ensures that platform setup was not attempted before the failure.
    mock_forward.assert_not_called()
