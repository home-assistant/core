"""Tests for Google Tasks."""

from collections.abc import Awaitable, Callable
import http
from http import HTTPStatus
import json
import time
from unittest.mock import Mock

from aiohttp import ClientError
from httplib2 import Response
import pytest

from homeassistant.components.google_tasks import DOMAIN
from homeassistant.components.google_tasks.const import OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import LIST_TASK_LIST_RESPONSE, LIST_TASKS_RESPONSE_WATER

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    "api_responses", [[LIST_TASK_LIST_RESPONSE, LIST_TASKS_RESPONSE_WATER]]
)
async def test_setup(
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
    mock_http_response: Mock,
) -> None:
    """Test successful setup and unload."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.services.async_services().get(DOMAIN)


@pytest.mark.parametrize("expires_at", [time.time() - 86400], ids=["expired"])
@pytest.mark.parametrize(
    "api_responses", [[LIST_TASK_LIST_RESPONSE, LIST_TASKS_RESPONSE_WATER]]
)
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    setup_credentials: None,
    mock_http_response: Mock,
) -> None:
    """Test expired token is refreshed."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "expires_at": time.time() + 86400,
            "expires_in": 86400,
        },
    )

    await integration_setup()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data["token"]["access_token"] == "updated-access-token"
    assert config_entry.data["token"]["expires_in"] == 86400


@pytest.mark.parametrize(
    ("expires_at", "status", "exc", "expected_state"),
    [
        (
            time.time() - 86400,
            http.HTTPStatus.UNAUTHORIZED,
            None,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            time.time() - 86400,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            None,
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            time.time() - 86400,
            None,
            ClientError("error"),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["unauthorized", "internal_server_error", "client_error"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    setup_credentials: None,
    status: http.HTTPStatus | None,
    exc: Exception | None,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=status,
        exc=exc,
    )

    await integration_setup()

    assert config_entry.state is expected_state


@pytest.mark.parametrize(
    "response_handler",
    [
        ([(Response({"status": HTTPStatus.INTERNAL_SERVER_ERROR}), b"")]),
        # First request succeeds, second request fails
        (
            [
                (
                    Response({"status": HTTPStatus.OK}),
                    json.dumps(LIST_TASK_LIST_RESPONSE),
                ),
                (Response({"status": HTTPStatus.INTERNAL_SERVER_ERROR}), b""),
            ]
        ),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    mock_http_response: Mock,
    config_entry: MockConfigEntry,
) -> None:
    """Test an error returned by the server when setting up the platform."""

    assert not await integration_setup()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
