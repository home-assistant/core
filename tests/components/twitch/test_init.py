"""Tests for Twitch."""

import http
import time
from unittest.mock import AsyncMock, patch

from aiohttp.client_exceptions import ClientError
import pytest
from twitchAPI.object.api import FollowedChannel

from homeassistant.components.twitch.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.components.twitch.coordinator import TwitchUpdate
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import TwitchIterObject, setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_success(
    hass: HomeAssistant, config_entry: MockConfigEntry, twitch_mock: AsyncMock
) -> None:
    """Test successful setup and unload."""
    await setup_integration(hass, config_entry)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    assert not hass.services.async_services().get(DOMAIN)


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    twitch_mock: AsyncMock,
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
    twitch_mock: AsyncMock,
) -> None:
    """Test failure while refreshing expired token requiring reauth or retry."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=status,
    )
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].state is expected_state


async def test_expired_token_refresh_client_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, twitch_mock: AsyncMock
) -> None:
    """Test failure while refreshing token with a client error."""

    with patch(
        "homeassistant.components.twitch.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientError,
    ):
        config_entry.add_to_hass(hass)

        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify a transient failure has occurred
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.twitch.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_new_follow_syncs_config_entry(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Newly followed channel is added to the config entry options."""
    # config_entry starts with only "internetofthings"
    # get_followed_channels fixture returns "internetofthings" + "homeassistant"
    # → coordinator must detect the delta and update the config entry

    await setup_integration(hass, config_entry)
    await hass.async_block_till_done()

    assert set(config_entry.options["channels"]) == {
        "internetofthings",
        "homeassistant",
    }
    assert config_entry.state is ConfigEntryState.LOADED


async def test_unfollowed_channel_stays_in_config(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
) -> None:
    """Unfollowed channel is kept in config entry options and continues to be tracked."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        unique_id="123",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": time.time() + 3600,
                "scope": "user:read:follows user:read:subscriptions",
            },
        },
        options={"channels": ["internetofthings", "homeassistant"]},
    )
    # API returns only "internetofthings" → "homeassistant" was unfollowed
    # but should remain in the config so it keeps being tracked.
    twitch_mock.return_value.get_followed_channels.return_value = TwitchIterObject(
        hass, "get_followed_channels_single.json", FollowedChannel
    )

    await setup_integration(hass, entry)
    await hass.async_block_till_done()

    # "homeassistant" must still be in channels — removals are ignored
    assert set(entry.options["channels"]) == {"internetofthings", "homeassistant"}
    assert entry.state is ConfigEntryState.LOADED


async def test_unchanged_follows_no_config_update(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
) -> None:
    """When followed channels match the config, no config update is triggered."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        unique_id="123",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": time.time() + 3600,
                "scope": "user:read:follows user:read:subscriptions",
            },
        },
        # Channels already match what get_followed_channels.json returns
        options={"channels": ["internetofthings", "homeassistant"]},
    )

    with patch.object(
        hass.config_entries,
        "async_update_entry",
        wraps=hass.config_entries.async_update_entry,
    ) as mock_update:
        await setup_integration(hass, entry)
        await hass.async_block_till_done()

    # async_update_entry must not have been called for options changes
    options_calls = [c for c in mock_update.call_args_list if "options" in c.kwargs]
    assert options_calls == [], (
        "config entry options must not be updated when channels are in sync"
    )
    assert entry.state is ConfigEntryState.LOADED


async def test_new_follow_creates_entity_at_runtime(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """New sensor entity is created at runtime when coordinator data gains a channel."""
    # Start with the default fixture — config_entry has only "internetofthings",
    # but the API mock returns both "internetofthings" and "homeassistant".
    # After the first refresh, the coordinator data will contain both.
    await setup_integration(hass, config_entry)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    initial_entities = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    initial_ids = {e.unique_id for e in initial_entities}

    # Inject a brand-new channel into coordinator data and fire listeners.
    coordinator = config_entry.runtime_data
    new_data = dict(coordinator.data)
    new_data["999"] = TwitchUpdate(
        name="NewChannel",
        followers=50,
        is_streaming=False,
        game=None,
        title=None,
        started_at=None,
        stream_picture=None,
        picture="logo.png",
        subscribed=None,
        subscription_gifted=None,
        subscription_tier=None,
        follows=True,
        following_since=None,
        viewers=None,
    )
    coordinator.async_set_updated_data(new_data)
    await hass.async_block_till_done()

    updated_entities = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    updated_ids = {e.unique_id for e in updated_entities}

    # The listener must have created a new entity for channel "999".
    assert "999" not in initial_ids
    assert "999" in updated_ids
