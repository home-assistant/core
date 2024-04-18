"""Tests for the oncue component."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from aiooncue import LoginFailedException

from homeassistant.components import oncue
from homeassistant.components.oncue.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import _patch_login_and_data, _patch_login_and_data_auth_failure

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_config_entry_reload(hass: HomeAssistant) -> None:
    """Test that a config entry can be reloaded."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "any", CONF_PASSWORD: "any"},
        unique_id="any",
    )
    config_entry.add_to_hass(hass)
    with _patch_login_and_data():
        await async_setup_component(hass, oncue.DOMAIN, {oncue.DOMAIN: {}})
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_login_error(hass: HomeAssistant) -> None:
    """Test that a config entry is failed on login error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "any", CONF_PASSWORD: "any"},
        unique_id="any",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.oncue.Oncue.async_login",
        side_effect=LoginFailedException,
    ):
        await async_setup_component(hass, oncue.DOMAIN, {oncue.DOMAIN: {}})
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_config_entry_retry_later(hass: HomeAssistant) -> None:
    """Test that a config entry retry on connection error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "any", CONF_PASSWORD: "any"},
        unique_id="any",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.oncue.Oncue.async_login",
        side_effect=TimeoutError,
    ):
        await async_setup_component(hass, oncue.DOMAIN, {oncue.DOMAIN: {}})
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_late_auth_failure(hass: HomeAssistant) -> None:
    """Test auth fails after already setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "any", CONF_PASSWORD: "any"},
        unique_id="any",
    )
    config_entry.add_to_hass(hass)
    with _patch_login_and_data():
        await async_setup_component(hass, oncue.DOMAIN, {oncue.DOMAIN: {}})
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    with _patch_login_and_data_auth_failure():
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    flow = flows[0]
    assert flow["context"]["source"] == "reauth"
