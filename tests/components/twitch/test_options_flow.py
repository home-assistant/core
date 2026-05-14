"""Tests for the Twitch options flow."""

import time
from unittest.mock import AsyncMock

from twitchAPI.object.api import FollowedChannel

from homeassistant.components.twitch.const import CONF_CLEANUP_UNFOLLOWED, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import TwitchIterObject, setup_integration

from tests.common import MockConfigEntry


async def test_options_flow_default_disabled(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test options flow shows cleanup_unfollowed defaulting to False."""
    await setup_integration(hass, config_entry)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    schema_keys = {str(k) for k in result["data_schema"].schema}
    assert CONF_CLEANUP_UNFOLLOWED in schema_keys


async def test_options_flow_enable_cleanup(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test enabling cleanup_unfollowed via options flow."""
    await setup_integration(hass, config_entry)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_CLEANUP_UNFOLLOWED: True}
    )
    assert result["type"] == "create_entry"
    assert config_entry.options[CONF_CLEANUP_UNFOLLOWED] is True


async def test_cleanup_removes_unfollowed_entity(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
) -> None:
    """Unfollowed channel entity is removed from registry when cleanup is enabled."""
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
        options={
            "channels": ["internetofthings", "homeassistant"],
            CONF_CLEANUP_UNFOLLOWED: True,
        },
    )
    # API now returns only "internetofthings" → "homeassistant" was unfollowed
    twitch_mock.return_value.get_followed_channels.return_value = TwitchIterObject(
        hass, "get_followed_channels_single.json", FollowedChannel
    )

    # Pre-register the "homeassistant" entity (broadcaster_id 456) so it
    # actually exists in the registry before cleanup runs.
    entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create("sensor", DOMAIN, "456", config_entry=entry)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    remaining_unique_ids = {e.unique_id for e in entries}

    # "456" should have been removed by the cleanup logic
    assert "456" not in remaining_unique_ids


async def test_no_cleanup_keeps_unfollowed_entity(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
) -> None:
    """Unfollowed channel entity stays in registry when cleanup is disabled."""
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
        options={
            "channels": ["internetofthings", "homeassistant"],
            CONF_CLEANUP_UNFOLLOWED: False,
        },
    )
    # API now returns only "internetofthings" → "homeassistant" was unfollowed
    twitch_mock.return_value.get_followed_channels.return_value = TwitchIterObject(
        hass, "get_followed_channels_single.json", FollowedChannel
    )
    # Pre-register the "homeassistant" entity so we can check it survives
    entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create("sensor", DOMAIN, "456", config_entry=entry)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    remaining_unique_ids = {e.unique_id for e in entries}
    assert "456" in remaining_unique_ids


async def test_runtime_cleanup_removes_entity(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
) -> None:
    """Entity is removed from registry at runtime when channel disappears from data."""
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
        options={
            "channels": ["internetofthings", "homeassistant"],
            CONF_CLEANUP_UNFOLLOWED: True,
        },
    )
    await setup_integration(hass, entry)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    entity_registry = er.async_get(hass)

    # Both channels should have entities after setup.
    initial = {
        e.unique_id
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }
    assert "123" in initial

    # Simulate a coordinator refresh where channel "123" is gone.
    reduced = {cid: data for cid, data in coordinator.data.items() if cid != "123"}
    coordinator.async_set_updated_data(reduced)
    await hass.async_block_till_done()

    remaining = {
        e.unique_id
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }
    assert "123" not in remaining
