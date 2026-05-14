"""Tests for the Twitch scan interval options flow."""

import time
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.twitch.const import (
    CONF_CLEANUP_UNFOLLOWED,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_options_flow_shows_scan_interval(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test options flow shows scan_interval field."""
    await setup_integration(hass, config_entry)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    schema_keys = {str(k) for k in result["data_schema"].schema}
    assert CONF_SCAN_INTERVAL in schema_keys


async def test_options_flow_default_scan_interval(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test default scan interval is 5 minutes."""
    await setup_integration(hass, config_entry)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    # Find the scan_interval key and check its default
    for key in result["data_schema"].schema:
        if str(key) == CONF_SCAN_INTERVAL:
            assert key.default() == DEFAULT_SCAN_INTERVAL
            break
    else:
        pytest.fail("scan_interval not found in options schema")


async def test_options_flow_set_scan_interval(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test setting a custom scan interval."""
    await setup_integration(hass, config_entry)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SCAN_INTERVAL: 15, CONF_CLEANUP_UNFOLLOWED: False},
    )
    assert result["type"] == "create_entry"
    assert config_entry.options[CONF_SCAN_INTERVAL] == 15


async def test_coordinator_uses_custom_scan_interval(
    hass: HomeAssistant,
    twitch_mock: AsyncMock,
) -> None:
    """Test coordinator respects scan_interval from options."""
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
        options={"channels": ["internetofthings"], CONF_SCAN_INTERVAL: 30},
    )
    await setup_integration(hass, entry)

    coordinator = entry.runtime_data
    assert coordinator.update_interval.total_seconds() == 30 * 60
