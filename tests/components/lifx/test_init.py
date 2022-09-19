"""Tests for the lifx component."""
from __future__ import annotations

from datetime import timedelta
import socket
from unittest.mock import patch

from homeassistant.components import lifx
from homeassistant.components.lifx import DOMAIN, discovery
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STARTED
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    IP_ADDRESS,
    SERIAL,
    MockFailingLifxCommand,
    _mocked_bulb,
    _mocked_failing_bulb,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_configuring_lifx_causes_discovery(hass):
    """Test that specifying empty config does discovery."""
    start_calls = 0

    class MockLifxDiscovery:
        """Mock lifx discovery."""

        def __init__(self, *args, **kwargs):
            """Init discovery."""
            discovered = _mocked_bulb()
            self.lights = {discovered.mac_addr: discovered}

        def start(self):
            """Mock start."""
            nonlocal start_calls
            start_calls += 1

        def cleanup(self):
            """Mock cleanup."""

    with _patch_config_flow_try_connect(), patch.object(
        discovery, "DEFAULT_TIMEOUT", 0
    ), patch(
        "homeassistant.components.lifx.discovery.LifxDiscovery", MockLifxDiscovery
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        assert start_calls == 0

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert start_calls == 1

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
        await hass.async_block_till_done()
        assert start_calls == 2

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=15))
        await hass.async_block_till_done()
        assert start_calls == 3

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=30))
        await hass.async_block_till_done()
        assert start_calls == 4


async def test_config_entry_reload(hass):
    """Test that a config entry can be reloaded."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    with _patch_discovery(), _patch_config_flow_try_connect(), _patch_device():
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        assert already_migrated_config_entry.state == ConfigEntryState.LOADED
        await hass.config_entries.async_unload(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()
        assert already_migrated_config_entry.state == ConfigEntryState.NOT_LOADED


async def test_config_entry_retry(hass):
    """Test that a config entry can be retried."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    with _patch_discovery(no_device=True), _patch_config_flow_try_connect(
        no_device=True
    ), _patch_device(no_device=True):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        assert already_migrated_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_get_version_fails(hass):
    """Test we handle get version failing."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.product = None
    bulb.host_firmware_version = None
    bulb.get_version = MockFailingLifxCommand(bulb)

    with _patch_discovery(device=bulb), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        assert already_migrated_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_dns_error_at_startup(hass):
    """Test we handle get version failing."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_failing_bulb()

    class MockLifxConnectonDnsError:
        """Mock lifx connection with a dns error."""

        def __init__(self, *args, **kwargs):
            """Init connection."""
            self.device = bulb

        async def async_setup(self):
            """Mock setup."""
            raise socket.gaierror()

        def async_stop(self):
            """Mock teardown."""

    # Cannot connect due to dns error
    with _patch_discovery(device=bulb), patch(
        "homeassistant.components.lifx.LIFXConnection",
        MockLifxConnectonDnsError,
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        assert already_migrated_config_entry.state == ConfigEntryState.SETUP_RETRY
