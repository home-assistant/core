"""Test Volvo init."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus

import pytest
from volvocarsapi.auth import TOKEN_URL

from homeassistant.components.volvo.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from .const import MOCK_ACCESS_TOKEN, SERVER_TOKEN_RESPONSE

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test setting up the integration."""
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    assert await setup_integration()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_token_refresh_success(
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test where token refresh succeeds."""

    assert mock_config_entry.data[CONF_TOKEN]["access_token"] == MOCK_ACCESS_TOKEN

    assert await setup_integration()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify token
    assert len(aioclient_mock.mock_calls) == 1
    assert (
        mock_config_entry.data[CONF_TOKEN]["access_token"]
        == SERVER_TOKEN_RESPONSE["access_token"]
    )


@pytest.mark.parametrize(
    ("token_response"),
    [
        (HTTPStatus.BAD_REQUEST),
        (HTTPStatus.FORBIDDEN),
        (HTTPStatus.INTERNAL_SERVER_ERROR),
        (HTTPStatus.NOT_FOUND),
    ],
)
async def test_token_refresh_fail(
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: Callable[[], Awaitable[bool]],
    token_response: HTTPStatus,
) -> None:
    """Test where token refresh fails."""

    aioclient_mock.post(TOKEN_URL, status=token_response)

    assert not await setup_integration()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_token_refresh_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test where token refresh indicates unauthorized."""

    aioclient_mock.post(TOKEN_URL, status=HTTPStatus.UNAUTHORIZED)

    assert not await setup_integration()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert flows
    assert flows[0]["handler"] == DOMAIN
    assert flows[0]["step_id"] == "reauth_confirm"
