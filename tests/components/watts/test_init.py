"""Test the Watts Vision integration initialization."""

from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError, ClientResponseError
import pytest
from visionpluspython.exceptions import (
    WattsVisionAuthError,
    WattsVisionConnectionError,
    WattsVisionDeviceError,
    WattsVisionError,
    WattsVisionTimeoutError,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload of entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_watts_client.discover_devices.assert_called_once()

    unload_result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert unload_result is True
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup with authentication failure."""

    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_implementation,
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
    ):
        mock_implementation = AsyncMock()
        mock_implementation.client_id = "test-client-id"
        mock_implementation.client_secret = "test-client-secret"
        mock_get_implementation.return_value = mock_implementation

        # Raise 401 error
        mock_session_instance = AsyncMock()
        mock_session_instance.async_ensure_token_valid.side_effect = (
            ClientResponseError(Mock(), Mock(), status=401, message="Unauthorized")
        )
        mock_session_instance.token = mock_config_entry.data["token"]
        mock_session.return_value = mock_session_instance

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is False
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup when network is temporarily unavailable."""

    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_implementation,
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
    ):
        mock_implementation = AsyncMock()
        mock_implementation.client_id = "test-client-id"
        mock_implementation.client_secret = "test-client-secret"
        mock_get_implementation.return_value = mock_implementation

        mock_session_instance = AsyncMock()
        mock_session_instance.async_ensure_token_valid.side_effect = ClientError(
            "Connection timeout"
        )
        mock_session_instance.token = mock_config_entry.data["token"]
        mock_session.return_value = mock_session_instance

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is False
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_hub_coordinator_update_failed(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup when hub coordinator update fails."""

    # Make discover_devices fail
    mock_watts_client.discover_devices.side_effect = ConnectionError("API error")

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_server_error_5xx(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup when server returns error."""

    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_implementation,
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
    ):
        mock_implementation = AsyncMock()
        mock_implementation.client_id = "test-client-id"
        mock_implementation.client_secret = "test-client-secret"
        mock_get_implementation.return_value = mock_implementation

        mock_session_instance = AsyncMock()
        mock_session_instance.async_ensure_token_valid.side_effect = (
            ClientResponseError(
                Mock(), Mock(), status=500, message="Internal Server Error"
            )
        )
        mock_session_instance.token = mock_config_entry.data["token"]
        mock_session.return_value = mock_session_instance

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is False
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (WattsVisionAuthError("Auth failed"), ConfigEntryState.SETUP_ERROR),
        (WattsVisionConnectionError("Connection lost"), ConfigEntryState.SETUP_RETRY),
        (WattsVisionTimeoutError("Request timeout"), ConfigEntryState.SETUP_RETRY),
        (WattsVisionDeviceError("Device error"), ConfigEntryState.SETUP_RETRY),
        (WattsVisionError("API error"), ConfigEntryState.SETUP_RETRY),
        (ValueError("Value error"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_discover_devices_errors(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup errors during device discovery."""
    mock_watts_client.discover_devices.side_effect = exception

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is expected_state
