"""Test init of senz integration."""

from http import HTTPStatus
import time
from unittest.mock import MagicMock, Mock, patch

from aiosenz import TOKEN_ENDPOINT
from httpx import HTTPStatusError, RequestError
import pytest

from homeassistant.components.senz.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import setup_integration
from .const import ENTRY_UNIQUE_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_senz_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    entry = mock_config_entry

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_oauth_implementation_not_available(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that an unavailable OAuth implementation raises ConfigEntryNotReady."""

    with patch(
        "homeassistant.components.senz.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_senz_client: MagicMock,
    expires_at: float,
    access_token: str,
) -> None:
    """Test migration of config entry."""
    mock_entry_v1_1 = MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="SENZ test",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": access_token,
                "scope": "rest_api offline_access",
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "token_type": "Bearer",
                "expires_at": expires_at,
            },
        },
        entry_id="senz_test",
    )

    await setup_integration(hass, mock_entry_v1_1)
    assert mock_entry_v1_1.version == 1
    assert mock_entry_v1_1.minor_version == 2
    assert mock_entry_v1_1.unique_id == ENTRY_UNIQUE_ID


@pytest.mark.parametrize(
    ("expires_at", "status", "expected_state"),
    [
        (
            time.time() - 3600,
            HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            time.time() - 3600,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
    ids=["unauthorized", "internal_server_error"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        TOKEN_ENDPOINT,
        status=status,
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        (
            HTTPStatusError(
                message="Exception",
                request=Mock(),
                response=MagicMock(status_code=HTTPStatus.UNAUTHORIZED),
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            HTTPStatusError(
                message="Exception",
                request=Mock(),
                response=MagicMock(status_code=HTTPStatus.FORBIDDEN),
            ),
            ConfigEntryState.SETUP_RETRY,
        ),
        (RequestError("Exception"), ConfigEntryState.SETUP_RETRY),
    ],
    ids=["unauthorized", "forbidden", "request_error"],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_senz_client: MagicMock,
    error: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup failure due to unauthorized error."""
    mock_senz_client.get_account.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state
