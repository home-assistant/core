"""Tests for the flux_led component."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components import flux_led
from homeassistant.components.flux_led.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_NAME, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import (
    DEFAULT_ENTRY_TITLE,
    DEFAULT_ENTRY_TITLE_PARTIAL,
    FLUX_DISCOVERY,
    FLUX_DISCOVERY_PARTIAL,
    IP_ADDRESS,
    MAC_ADDRESS,
    _patch_discovery,
    _patch_wifibulb,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_configuring_flux_led_causes_discovery(hass: HomeAssistant) -> None:
    """Test that specifying empty config does discovery."""
    with patch(
        "homeassistant.components.flux_led.AIOBulbScanner.async_scan"
    ) as discover:
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


@pytest.mark.parametrize(
    "discovery,title",
    [
        (FLUX_DISCOVERY, DEFAULT_ENTRY_TITLE),
        (FLUX_DISCOVERY_PARTIAL, DEFAULT_ENTRY_TITLE_PARTIAL),
    ],
)
async def test_config_entry_fills_unique_id_with_directed_discovery(
    hass: HomeAssistant, discovery: dict[str, str], title: str
) -> None:
    """Test that the unique id is added if its missing via directed (not broadcast) discovery."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=None
    )
    config_entry.add_to_hass(hass)

    async def _discovery(self, *args, address=None, **kwargs):
        # Only return discovery results when doing directed discovery
        return [discovery] if address == IP_ADDRESS else []

    with patch(
        "homeassistant.components.flux_led.AIOBulbScanner.async_scan", new=_discovery
    ), _patch_wifibulb():
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED

    assert config_entry.unique_id == MAC_ADDRESS
    assert config_entry.data[CONF_NAME] == title
    assert config_entry.title == title
