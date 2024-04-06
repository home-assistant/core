"""Test fitbit component."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus

import pytest
from requests_mock.mocker import Mocker

from homeassistant.components.fitbit.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import (
    CLIENT_ID,
    CLIENT_SECRET,
    DEVICES_API_URL,
    FAKE_ACCESS_TOKEN,
    FAKE_REFRESH_TOKEN,
    SERVER_ACCESS_TOKEN,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup(
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """Test setting up the integration."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("token_expiration_time", "server_status"),
    [
        (12345, HTTPStatus.INTERNAL_SERVER_ERROR),
        (12345, HTTPStatus.FORBIDDEN),
        (12345, HTTPStatus.NOT_FOUND),
    ],
)
async def test_token_refresh_failure(
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
    server_status: HTTPStatus,
) -> None:
    """Test where token is expired and the refresh attempt fails and will be retried."""

    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=server_status,
    )

    assert not await integration_setup()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("token_expiration_time", [12345])
async def test_token_refresh_success(
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
) -> None:
    """Test where token is expired and the refresh attempt succeeds."""

    assert config_entry.data["token"]["access_token"] == FAKE_ACCESS_TOKEN

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json=SERVER_ACCESS_TOKEN,
    )

    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    # Verify token request
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == {
        CONF_CLIENT_ID: CLIENT_ID,
        CONF_CLIENT_SECRET: CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": FAKE_REFRESH_TOKEN,
    }

    # Verify updated token
    assert (
        config_entry.data["token"]["access_token"]
        == SERVER_ACCESS_TOKEN["access_token"]
    )


@pytest.mark.parametrize(
    ("token_expiration_time", "server_status"),
    [
        (12345, HTTPStatus.UNAUTHORIZED),
        (12345, HTTPStatus.BAD_REQUEST),
    ],
)
@pytest.mark.parametrize("closing", [True, False])
async def test_token_requires_reauth(
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
    server_status: HTTPStatus,
    closing: bool,
) -> None:
    """Test where token is expired and the refresh attempt requires reauth."""

    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=server_status,
        closing=closing,
    )

    assert not await integration_setup()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_device_update_coordinator_failure(
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    requests_mock: Mocker,
) -> None:
    """Test case where the device update coordinator fails on the first request."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    requests_mock.register_uri(
        "GET",
        DEVICES_API_URL,
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    assert not await integration_setup()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_update_coordinator_reauth(
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    requests_mock: Mocker,
) -> None:
    """Test case where the device update coordinator fails on the first request."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    requests_mock.register_uri(
        "GET",
        DEVICES_API_URL,
        status_code=HTTPStatus.UNAUTHORIZED,
        json={
            "errors": [{"errorType": "invalid_grant"}],
        },
    )

    assert not await integration_setup()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
