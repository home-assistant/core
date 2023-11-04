"""Tests for YouTube."""
import http
import time
from unittest.mock import patch

from aiohttp.client_exceptions import ClientError
import pytest
from twitchAPI.twitch import TwitchAPIException, TwitchAuthorizationException

from homeassistant.components.twitch.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    TwitchAPIExceptionMock,
    TwitchBackendExceptionMock,
    TwitchInvalidUserMock,
    TwitchMock,
    setup_integration,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_success(
    hass: HomeAssistant, config_entry: MockConfigEntry, twitch: TwitchMock
) -> None:
    """Test successful setup and unload."""
    await setup_integration(hass, config_entry)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    assert not hass.services.async_services().get(DOMAIN)


async def test_disabled_entity(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test disabled entity."""
    await setup_integration(hass, config_entry)

    entity_registry = er.async_get(hass)
    entity_id = "sensor.channel123"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled_by is None

    assert entity.config_entry_id is not None

    entity_registry.async_update_entity(
        entity_id=entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    # Update coordinator to ensure entities are removed
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled_by == er.RegistryEntryDisabler.USER


async def test_coordinator_update_authorization_error(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test coordinator update errors."""
    await setup_integration(hass, config_entry)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    with patch(
        "homeassistant.components.twitch.coordinator.TwitchUpdateCoordinator._async_get_data",
        side_effect=TwitchAuthorizationException,
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()


async def test_coordinator_update_api_error(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test coordinator update errors."""
    await setup_integration(hass, config_entry)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    with patch(
        "homeassistant.components.twitch.coordinator.TwitchUpdateCoordinator._async_get_data",
        side_effect=TwitchAPIException,
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    twitch: TwitchMock,
) -> None:
    """Test expired token is refreshed."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "expires_at": time.time() + 3600,
            "expires_in": 3600,
        },
    )

    await setup_integration(hass, config_entry)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert entries[0].data["token"]["access_token"] == "updated-access-token"
    assert entries[0].data["token"]["expires_in"] == 3600


@pytest.mark.parametrize(
    ("expires_at", "status", "expected_state"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["failure_requires_reauth", "transient_failure"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
    config_entry: MockConfigEntry,
    twitch: TwitchMock,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=status,
    )

    await setup_integration(hass, config_entry)

    # Verify a transient failure has occurred
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].state is expected_state


async def test_expired_token_refresh_client_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, twitch: TwitchMock
) -> None:
    """Test failure while refreshing token with a client error."""

    with patch(
        "homeassistant.components.twitch.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientError,
    ):
        await setup_integration(hass, config_entry)

    # Verify a transient failure has occurred
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("twitch_mock", [TwitchInvalidUserMock()])
async def test_auth_with_invalid_user(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test auth with invalid user."""
    await setup_integration(hass, config_entry)


@pytest.mark.parametrize("twitch_mock", [TwitchAPIExceptionMock()])
async def test_auth_with_api_exception(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test auth with invalid user."""
    await setup_integration(hass, config_entry)


@pytest.mark.parametrize("twitch_mock", [TwitchBackendExceptionMock()])
async def test_auth_with_backend_exception(
    hass: HomeAssistant, twitch: TwitchMock, config_entry: MockConfigEntry
) -> None:
    """Test auth with invalid user."""
    await setup_integration(hass, config_entry)
