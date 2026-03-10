"""Advanced tests for LoJack integration initialization."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import MockApiError

from tests.common import MockConfigEntry


async def test_setup_entry_list_devices_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails gracefully if list_devices raises ApiError."""
    client = AsyncMock()
    client.list_devices = AsyncMock(side_effect=MockApiError("API error"))
    client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.ApiError",
            MockApiError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    client.close.assert_called_once()


async def test_setup_entry_close_fails_after_list_devices_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when list_devices fails, even if close also fails."""
    client = AsyncMock()
    client.list_devices = AsyncMock(side_effect=MockApiError("API error"))
    client.close = AsyncMock(side_effect=Exception("Close failed"))

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.ApiError",
            MockApiError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry_platforms_unload_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test unload handles platform unload failures."""
    await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)

    # Should return False if platform unload fails
    assert result is False
    # Client close should not be called if platform unload fails
    mock_lojack_client.close.assert_not_called()


async def test_setup_entry_generic_exception_during_client_create(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup handles unexpected exceptions during client creation."""
    with patch(
        "homeassistant.components.lojack.LoJackClient.create",
        side_effect=ValueError("Unexpected error"),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Unexpected exceptions should propagate as setup error
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_and_then_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test setup entry followed by reload."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_lojack_client.reset_mock()
    # Reset context manager mocks too
    mock_lojack_client.__aenter__ = AsyncMock(return_value=mock_lojack_client)
    mock_lojack_client.__aexit__ = AsyncMock(return_value=False)

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_lojack_client.close.assert_called_once()
