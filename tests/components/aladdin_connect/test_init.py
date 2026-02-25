"""Tests for the Aladdin Connect integration."""

import http
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError, RequestInfo
from aiohttp.client_exceptions import ClientResponseError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a successful setup entry."""
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a successful unload entry."""
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        (http.HTTPStatus.UNAUTHORIZED, ConfigEntryState.SETUP_ERROR),
        (http.HTTPStatus.INTERNAL_SERVER_ERROR, ConfigEntryState.SETUP_RETRY),
    ],
    ids=["auth_failure", "server_error"],
)
async def test_setup_entry_token_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup entry fails when token validation fails."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientResponseError(
            RequestInfo("", "POST", {}, ""), None, status=status
        ),
    ):
        await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_setup_entry_token_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup entry retries when token validation has a connection error."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientConnectionError(),
    ):
        await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        (http.HTTPStatus.UNAUTHORIZED, ConfigEntryState.SETUP_ERROR),
        (http.HTTPStatus.INTERNAL_SERVER_ERROR, ConfigEntryState.SETUP_RETRY),
    ],
    ids=["auth_failure", "server_error"],
)
async def test_setup_entry_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aladdin_connect_api: AsyncMock,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup entry fails when API call fails."""
    mock_aladdin_connect_api.get_doors.side_effect = ClientResponseError(
        RequestInfo("", "GET", {}, ""), None, status=status
    )
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is expected_state


async def test_setup_entry_api_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aladdin_connect_api: AsyncMock,
) -> None:
    """Test setup entry retries when API has a connection error."""
    mock_aladdin_connect_api.get_doors.side_effect = ClientConnectionError()
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
