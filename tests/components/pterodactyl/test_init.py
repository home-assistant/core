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
    ("api_error", "expected_state", "expected_flow_sources"),
    [
        pytest.param(
            PterodactylApiError,
            ConfigEntryState.SETUP_RETRY,
            [],
            id="pterodactyl_api_error",
        ),
        pytest.param(
            BadRequestError,
            ConfigEntryState.SETUP_RETRY,
            [],
            id="bad_request_error",
        ),
        pytest.param(
            ClientError,
            ConfigEntryState.SETUP_RETRY,
            [],
            id="client_error",
        ),
        pytest.param(
            TimeoutError,
            ConfigEntryState.SETUP_RETRY,
            [],
            id="timeout",
        ),
        pytest.param(
            ClientResponseError(
                request_info=Mock(real_url=URL(TEST_URL)),
                history=[],
                status=500,
            ),
            ConfigEntryState.SETUP_RETRY,
            [],
            id="http_error",
        ),
        pytest.param(
            ClientResponseError(
                request_info=Mock(real_url=URL(TEST_URL)),
                history=[],
                status=401,
            ),
            ConfigEntryState.SETUP_ERROR,
            [SOURCE_REAUTH],
            id="auth_error",
        ),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
    api_error: Exception | type[Exception],
    expected_state: ConfigEntryState,
    expected_flow_sources: list[str],
) -> None:
    """Test setup errors are handled correctly."""
    mock_pterodactyl.client.servers.list_servers.side_effect = api_error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == expected_flow_sources
