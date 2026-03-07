"""Advanced tests for LoJack integration initialization."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryState

from . import setup_integration
from .conftest import MockApiError, MockAuthenticationError

from tests.common import MockConfigEntry


async def test_setup_entry_with_first_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails gracefully if first refresh fails."""
    client = AsyncMock()
    client.list_devices = AsyncMock(side_effect=MockApiError("API error"))
    client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.ApiError",
            MockApiError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
        client.close.assert_called_once()


async def test_setup_entry_close_fails_after_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when refresh fails, even if close also fails."""
    client = AsyncMock()
    client.list_devices = AsyncMock(side_effect=MockApiError("API error"))
    client.close = AsyncMock(side_effect=Exception("Close failed"))

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.ApiError",
            MockApiError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # close() failure is caught in the finally block, so the original
        # ApiError propagates as UpdateFailed → SETUP_RETRY
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_token_refresh_client_close_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: AsyncMock,
    mock_location: AsyncMock,
) -> None:
    """Test coordinator handles old client close failure during token refresh."""
    mock_device.get_location = AsyncMock(return_value=mock_location)

    old_client = AsyncMock()
    old_client.list_devices = AsyncMock(side_effect=MockAuthenticationError("Token expired"))
    old_client.close = AsyncMock(side_effect=Exception("Close failed"))

    new_client = AsyncMock()
    new_client.list_devices = AsyncMock(return_value=[mock_device])
    new_client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            side_effect=[old_client, new_client],
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=old_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=new_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.AuthenticationError",
            MockAuthenticationError,
        ),
    ):
        await setup_integration(hass, mock_config_entry)

        coordinator = mock_config_entry.runtime_data
        assert coordinator.data is not None


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
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_lojack_client.close.assert_called_once()
