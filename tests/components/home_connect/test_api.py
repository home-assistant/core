"""Test the API driver code."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from unittest.mock import patch

from homeconnect import HomeConnectAPI
import pytest
import requests_mock

from homeassistant.components.home_connect.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import (
    CLIENT_ID,
    CLIENT_SECRET,
    FAKE_ACCESS_TOKEN,
    FAKE_REFRESH_TOKEN,
    SERVER_ACCESS_TOKEN,
    get_appliances,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_api_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
) -> None:
    """Test setup and unload."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED

    with patch.object(
        HomeConnectAPI,
        "get_appliances",
        side_effect=lambda: get_appliances(hass.data[DOMAIN][config_entry.entry_id]),
    ):
        assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_exceptions(
    bypass_throttle,
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    problematic_appliance,
) -> None:
    """Test exception handling."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    with patch.object(
        HomeConnectAPI, "get_appliances", return_value=[problematic_appliance]
    ):
        assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("token_expiration_time", "server_status"),
    [
        (12345, HTTPStatus.INTERNAL_SERVER_ERROR),
        (12345, HTTPStatus.FORBIDDEN),
        (12345, HTTPStatus.NOT_FOUND),
    ],
)
async def test_token_refresh_failure(
    bypass_throttle,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
    server_status: int,
) -> None:
    """Test where token is expired and the refresh attempt fails and will be retried."""

    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=server_status,
    )
    assert not await integration_setup()
    assert config_entry.state == ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize("token_expiration_time", [12345])
async def test_token_refresh_success(
    bypass_throttle,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    requests_mock: requests_mock.Mocker,
    setup_credentials: None,
) -> None:
    """Test where token is expired and the refresh attempt succeeds."""

    assert config_entry.data["token"]["access_token"] == FAKE_ACCESS_TOKEN

    requests_mock.post(OAUTH2_TOKEN, json=SERVER_ACCESS_TOKEN)
    requests_mock.get("/api/homeappliances", json={"data": {"homeappliances": []}})

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json=SERVER_ACCESS_TOKEN,
    )
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    # Verify token request
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": FAKE_REFRESH_TOKEN,
    }

    # Verify updated token
    assert (
        config_entry.data["token"]["access_token"]
        == SERVER_ACCESS_TOKEN["access_token"]
    )
