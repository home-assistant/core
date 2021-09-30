"""Tests for the flux_led component."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.components import flux_led
from homeassistant.components.flux_led.const import (
    CONF_COLORS,
    CONF_CUSTOM_EFFECT,
    CONF_CUSTOM_EFFECT_COLORS,
    CONF_CUSTOM_EFFECT_SPEED_PCT,
    CONF_CUSTOM_EFFECT_TRANSITION,
    CONF_DEVICES,
    CONF_SPEED_PCT,
    CONF_TRANSITION,
    DOMAIN,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PROTOCOL,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import FLUX_DISCOVERY, IP_ADDRESS, MAC_ADDRESS, _patch_discovery, _patch_wifibulb

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


async def test_migrate_from_yaml(hass: HomeAssistant) -> None:
    """Test migrate from yaml."""
    config = {
        LIGHT_DOMAIN: [
            {
                CONF_PLATFORM: DOMAIN,
                CONF_DEVICES: {
                    IP_ADDRESS: {
                        CONF_NAME: "flux_lamppost",
                        CONF_PROTOCOL: "ledenet",
                        CONF_CUSTOM_EFFECT: {
                            CONF_SPEED_PCT: 30,
                            CONF_TRANSITION: "strobe",
                            CONF_COLORS: [[255, 0, 0], [255, 255, 0], [0, 255, 0]],
                        },
                    }
                },
            },
            {
                CONF_PLATFORM: "anything else",
            },
        ],
        "garbage": [{}],
    }
    with _patch_discovery(), _patch_wifibulb():
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    migrated_entry = None
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id == MAC_ADDRESS:
            migrated_entry = entry
            break

    assert migrated_entry is not None
    assert migrated_entry.data == {
        CONF_HOST: IP_ADDRESS,
        CONF_NAME: "flux_lamppost",
        CONF_PROTOCOL: "ledenet",
    }
    assert migrated_entry.options == {
        CONF_MODE: "auto",
        CONF_CUSTOM_EFFECT_COLORS: "[[255, 0, 0], [255, 255, 0], [0, 255, 0]]",
        CONF_CUSTOM_EFFECT_SPEED_PCT: 30,
        CONF_CUSTOM_EFFECT_TRANSITION: "strobe",
    }
