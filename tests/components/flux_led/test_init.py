"""Tests for the flux_led component."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.components import flux_led
from homeassistant.components.flux_led.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import (
    FLUX_DISCOVERY,
    IP_ADDRESS,
    MAC_ADDRESS,
    _mocked_bulb,
    _patch_discovery,
    _patch_wifibulb,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_configuring_flux_led_causes_discovery(hass: HomeAssistant) -> None:
    """Test that specifying empty config does discovery."""
    with patch("homeassistant.components.flux_led.BulbScanner.scan") as discover:
        discover.return_value = [FLUX_DISCOVERY]
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

        assert len(discover.mock_calls) == 1
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert len(discover.mock_calls) == 2

        async_fire_time_changed(hass, utcnow() + flux_led.DISCOVERY_INTERVAL)
        await hass.async_block_till_done()
        assert len(discover.mock_calls) == 3


async def test_config_entry_reload(hass: HomeAssistant) -> None:
    """Test that a config entry can be reloaded."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=MAC_ADDRESS)
    config_entry.add_to_hass(hass)
    with _patch_discovery(), _patch_wifibulb():
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_config_entry_retry(hass: HomeAssistant) -> None:
    """Test that a config entry can be retried."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS
    )
    config_entry.add_to_hass(hass)
    with _patch_discovery(no_device=True), _patch_wifibulb(no_device=True):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_config_entry_retry_when_state_missing(hass: HomeAssistant) -> None:
    """Test that a config entry is retried when state is missing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.raw_state = None
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.SETUP_RETRY
