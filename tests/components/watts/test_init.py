"""Test the Watts Vision integration initialization."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest
from visionpluspython.exceptions import (
    WattsVisionAuthError,
    WattsVisionConnectionError,
    WattsVisionDeviceError,
    WattsVisionError,
    WattsVisionTimeoutError,
)

from homeassistant.components.watts.const import OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


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


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup with authentication failure."""
    config_entry = MockConfigEntry(
        domain="watts",
        unique_id="test-device-id",
        data={
            "device_id": "test-device-id",
            "auth_implementation": "watts",
            "token": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 0,  # Expired token to force refresh
            },
        },
    )
    config_entry.add_to_hass(hass)

    aioclient_mock.post(OAUTH2_TOKEN, status=401)

    result = await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup when network is temporarily unavailable."""
    config_entry = MockConfigEntry(
        domain="watts",
        unique_id="test-device-id",
        data={
            "device_id": "test-device-id",
            "auth_implementation": "watts",
            "token": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 0,  # Expired token to force refresh
            },
        },
    )
    config_entry.add_to_hass(hass)

    aioclient_mock.post(OAUTH2_TOKEN, exc=ClientError("Connection timeout"))

    result = await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


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


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_entry_server_error_5xx(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup when server returns error."""
    config_entry = MockConfigEntry(
        domain="watts",
        unique_id="test-device-id",
        data={
            "device_id": "test-device-id",
            "auth_implementation": "watts",
            "token": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 0,  # Expired token to force refresh
            },
        },
    )
    config_entry.add_to_hass(hass)

    aioclient_mock.post(OAUTH2_TOKEN, status=500)

    result = await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


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
