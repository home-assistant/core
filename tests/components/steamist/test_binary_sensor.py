"""Tests for the steamist binary_sensor."""
from __future__ import annotations

from homeassistant.components import steamist
from homeassistant.components.steamist.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import _patch_status_active, _patch_status_inactive

from tests.common import MockConfigEntry


async def test_steam_active(hass: HomeAssistant) -> None:
    """Test that the binary sensors are setup with the expected values when steam is active."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
    )
    config_entry.add_to_hass(hass)
    with _patch_status_active():
        await async_setup_component(hass, steamist.DOMAIN, {steamist.DOMAIN: {}})
        await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED

    assert len(hass.states.async_all("binary_sensor")) == 1
    assert hass.states.get("binary_sensor.steam_active").state == STATE_ON


async def test_steam_inactive(hass: HomeAssistant) -> None:
    """Test that the binary sensors are setup with the expected values when steam is not active."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
    )
    config_entry.add_to_hass(hass)
    with _patch_status_inactive():
        await async_setup_component(hass, steamist.DOMAIN, {steamist.DOMAIN: {}})
        await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED

    assert len(hass.states.async_all("binary_sensor")) == 1
    assert hass.states.get("binary_sensor.steam_active").state == STATE_OFF
