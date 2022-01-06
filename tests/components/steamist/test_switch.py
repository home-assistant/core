"""Tests for the steamist switch."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from homeassistant.components import steamist
from homeassistant.components.steamist.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import (
    MOCK_ASYNC_GET_STATUS_ACTIVE,
    MOCK_ASYNC_GET_STATUS_INACTIVE,
    _mocked_steamist,
    _patch_status_active,
    _patch_status_inactive,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_steam_active(hass: HomeAssistant) -> None:
    """Test that the binary sensors are setup with the expected values when steam is active."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
    )
    config_entry.add_to_hass(hass)
    client = _mocked_steamist()
    client.async_get_status = AsyncMock(return_value=MOCK_ASYNC_GET_STATUS_ACTIVE)
    with _patch_status_active(client):
        await async_setup_component(hass, steamist.DOMAIN, {steamist.DOMAIN: {}})
        await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED

    assert len(hass.states.async_all("switch")) == 1
    assert hass.states.get("switch.steam_active").state == STATE_ON

    client.async_get_status = AsyncMock(return_value=MOCK_ASYNC_GET_STATUS_INACTIVE)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: "switch.steam_active"},
        blocking=True,
    )
    client.async_turn_off_steam.assert_called_once()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    assert hass.states.get("switch.steam_active").state == STATE_OFF


async def test_steam_inactive(hass: HomeAssistant) -> None:
    """Test that the binary sensors are setup with the expected values when steam is not active."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
    )
    config_entry.add_to_hass(hass)
    client = _mocked_steamist()
    client.async_get_status = AsyncMock(return_value=MOCK_ASYNC_GET_STATUS_INACTIVE)
    with _patch_status_inactive(client):
        await async_setup_component(hass, steamist.DOMAIN, {steamist.DOMAIN: {}})
        await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED

    assert len(hass.states.async_all("switch")) == 1
    assert hass.states.get("switch.steam_active").state == STATE_OFF

    client.async_get_status = AsyncMock(return_value=MOCK_ASYNC_GET_STATUS_ACTIVE)
    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: "switch.steam_active"}, blocking=True
    )
    client.async_turn_on_steam.assert_called_once()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    assert hass.states.get("switch.steam_active").state == STATE_ON
