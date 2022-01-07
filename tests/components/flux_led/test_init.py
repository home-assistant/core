"""Tests for the flux_led component."""
from __future__ import annotations

from datetime import timedelta
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
    FLUX_DISCOVERY,
    FLUX_DISCOVERY_PARTIAL,
    IP_ADDRESS,
    MAC_ADDRESS,
    _mocked_bulb,
    _patch_discovery,
    _patch_wifibulb,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_single_broadcast_address")
async def test_configuring_flux_led_causes_discovery(hass: HomeAssistant) -> None:
    """Test that specifying empty config does discovery."""
    with patch(
        "homeassistant.components.flux_led.discovery.AIOBulbScanner.async_scan"
    ) as scan, patch(
        "homeassistant.components.flux_led.discovery.AIOBulbScanner.getBulbInfo"
    ) as discover:
        discover.return_value = [FLUX_DISCOVERY]
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

        assert len(scan.mock_calls) == 1
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert len(scan.mock_calls) == 2

        async_fire_time_changed(hass, utcnow() + flux_led.DISCOVERY_INTERVAL)
        await hass.async_block_till_done()
        assert len(scan.mock_calls) == 3


@pytest.mark.usefixtures("mock_multiple_broadcast_addresses")
async def test_configuring_flux_led_causes_discovery_multiple_addresses(
    hass: HomeAssistant,
) -> None:
    """Test that specifying empty config does discovery."""
    with patch(
        "homeassistant.components.flux_led.discovery.AIOBulbScanner.async_scan"
    ) as scan, patch(
        "homeassistant.components.flux_led.discovery.AIOBulbScanner.getBulbInfo"
    ) as discover:
        discover.return_value = [FLUX_DISCOVERY]
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

        assert len(scan.mock_calls) == 2
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert len(scan.mock_calls) == 4

        async_fire_time_changed(hass, utcnow() + flux_led.DISCOVERY_INTERVAL)
        await hass.async_block_till_done()
        assert len(scan.mock_calls) == 6


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
        (FLUX_DISCOVERY_PARTIAL, DEFAULT_ENTRY_TITLE),
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
    last_address = None

    async def _discovery(self, *args, address=None, **kwargs):
        # Only return discovery results when doing directed discovery
        nonlocal last_address
        last_address = address
        return [FLUX_DISCOVERY] if address == IP_ADDRESS else []

    def _mock_getBulbInfo(*args, **kwargs):
        nonlocal last_address
        return [FLUX_DISCOVERY] if last_address == IP_ADDRESS else []

    with patch(
        "homeassistant.components.flux_led.discovery.AIOBulbScanner.async_scan",
        new=_discovery,
    ), patch(
        "homeassistant.components.flux_led.discovery.AIOBulbScanner.getBulbInfo",
        new=_mock_getBulbInfo,
    ), _patch_wifibulb():
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED

    assert config_entry.unique_id == MAC_ADDRESS
    assert config_entry.data[CONF_NAME] == title
    assert config_entry.title == title


async def test_time_sync_startup_and_next_day(hass: HomeAssistant) -> None:
    """Test that time is synced on startup and next day."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=MAC_ADDRESS)
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED

    assert len(bulb.async_set_time.mock_calls) == 1
    async_fire_time_changed(hass, utcnow() + timedelta(hours=24))
    await hass.async_block_till_done()
    assert len(bulb.async_set_time.mock_calls) == 2
