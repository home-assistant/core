"""Tests for the Pterodactyl integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock

from aiohttp import ClientError, ClientResponseError
from pydactyl.exceptions import BadRequestError, PterodactylApiError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from yarl import URL

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import TEST_URL


@pytest.mark.parametrize(
    "api_error",
    [
        pytest.param(
            PterodactylApiError,
            id="pterodactyl_api_error",
        ),
        pytest.param(
            BadRequestError,
            id="bad_request_error",
        ),
        pytest.param(
            ClientError,
            id="client_error",
        ),
        pytest.param(
            TimeoutError,
            id="timeout",
        ),
        pytest.param(
            ClientResponseError(
                request_info=Mock(real_url=URL(TEST_URL)),
                history=[],
                status=500,
            ),
            id="http_error",
        ),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
    api_error: Exception | type[Exception],
) -> None:
    """Test setup connection errors are retried."""
    mock_pterodactyl.client.servers.list_servers.side_effect = api_error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.config_entries.flow.async_progress() == []


async def test_setup_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
) -> None:
    """Test setup authorization error start reauthentication."""
    mock_pterodactyl.client.servers.list_servers.side_effect = ClientResponseError(
        request_info=Mock(real_url=URL(TEST_URL)),
        history=[],
        status=401,
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]
