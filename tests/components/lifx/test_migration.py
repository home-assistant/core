"""Tests the lifx migration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from homeassistant import setup
from homeassistant.components import lifx
from homeassistant.components.lifx import DOMAIN, discovery
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    IP_ADDRESS,
    LABEL,
    MAC_ADDRESS,
    SERIAL,
    _mocked_bulb,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_migration_device_online_end_to_end(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from single config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, title="LEGACY", data={}, unique_id=DOMAIN
    )
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, SERIAL)},
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
        name=LABEL,
    )
    light_entity_reg = entity_registry.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="light",
        unique_id=dr.format_mac(SERIAL),
        original_name=LABEL,
        device_id=device.id,
    )

    with _patch_discovery(), _patch_config_flow_try_connect(), _patch_device():
        await setup.async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        migrated_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == DOMAIN:
                migrated_entry = entry
                break

        assert migrated_entry is not None

        assert device.config_entries == {migrated_entry.entry_id}
        assert light_entity_reg.config_entry_id == migrated_entry.entry_id
        assert er.async_entries_for_config_entry(entity_registry, config_entry) == []

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=20))
        await hass.async_block_till_done()

        legacy_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == DOMAIN:
                legacy_entry = entry
                break

        assert legacy_entry is None


async def test_discovery_is_more_frequent_during_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that discovery is more frequent during migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, title="LEGACY", data={}, unique_id=DOMAIN
    )
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, SERIAL)},
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
        name=LABEL,
    )
    entity_registry.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="light",
        unique_id=dr.format_mac(SERIAL),
        original_name=LABEL,
        device_id=device.id,
    )

    bulb = _mocked_bulb()
    start_calls = 0

    class MockLifxDiscovery:
        """Mock lifx discovery."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Init discovery."""
            self.bulb = bulb
            self.lights = {}

        def start(self):
            """Mock start."""
            nonlocal start_calls
            start_calls += 1
            # Discover the bulb so we can complete migration
            # and verify we switch back to normal discovery
            # interval
            if start_calls == 4:
                self.lights = {self.bulb.mac_addr: self.bulb}

        def cleanup(self):
            """Mock cleanup."""

    with (
        _patch_device(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        patch.object(discovery, "DEFAULT_TIMEOUT", 0),
        patch(
            "homeassistant.components.lifx.discovery.LifxDiscovery", MockLifxDiscovery
        ),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        assert start_calls == 0

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert start_calls == 1

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert start_calls == 3

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert start_calls == 4

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=15))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert start_calls == 5


async def test_migration_device_online_end_to_end_after_downgrade(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from single config entry can happen again after a downgrade."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, title="LEGACY", data={}, unique_id=DOMAIN
    )
    config_entry.add_to_hass(hass)

    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, SERIAL)},
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
        name=LABEL,
    )
    light_entity_reg = entity_registry.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="light",
        unique_id=SERIAL,
        original_name=LABEL,
        device_id=device.id,
    )

    with _patch_discovery(), _patch_config_flow_try_connect(), _patch_device():
        await setup.async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=20))
        await hass.async_block_till_done()

        assert device.config_entries == {config_entry.entry_id}
        assert light_entity_reg.config_entry_id == config_entry.entry_id
        assert er.async_entries_for_config_entry(entity_registry, config_entry) == []

        legacy_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == DOMAIN:
                legacy_entry = entry
                break

        assert legacy_entry is None


async def test_migration_device_online_end_to_end_ignores_other_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from single config entry."""
    legacy_config_entry = MockConfigEntry(
        domain=DOMAIN, title="LEGACY", data={}, unique_id=DOMAIN
    )
    legacy_config_entry.add_to_hass(hass)

    other_domain_config_entry = MockConfigEntry(
        domain="other_domain", data={}, unique_id="other_domain"
    )
    other_domain_config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=legacy_config_entry.entry_id,
        identifiers={(DOMAIN, SERIAL)},
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
        name=LABEL,
    )
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_domain_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "556655665566")},
        name=LABEL,
    )
    light_entity_reg = entity_registry.async_get_or_create(
        config_entry=legacy_config_entry,
        platform=DOMAIN,
        domain="light",
        unique_id=SERIAL,
        original_name=LABEL,
        device_id=device.id,
    )
    ignored_entity_reg = entity_registry.async_get_or_create(
        config_entry=other_domain_config_entry,
        platform=DOMAIN,
        domain="sensor",
        unique_id="00:00:00:00:00:00_sensor",
        original_name=LABEL,
        device_id=device.id,
    )
    garbage_entity_reg = entity_registry.async_get_or_create(
        config_entry=legacy_config_entry,
        platform=DOMAIN,
        domain="sensor",
        unique_id="garbage",
        original_name=LABEL,
        device_id=other_device.id,
    )

    with _patch_discovery(), _patch_config_flow_try_connect(), _patch_device():
        await setup.async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=20))
        await hass.async_block_till_done()

        new_entry = None
        legacy_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == DOMAIN:
                legacy_entry = entry
            else:
                new_entry = entry

        assert new_entry is not None
        assert legacy_entry is None

        assert device.config_entries == {legacy_config_entry.entry_id}
        assert light_entity_reg.config_entry_id == legacy_config_entry.entry_id
        assert ignored_entity_reg.config_entry_id == other_domain_config_entry.entry_id
        assert garbage_entity_reg.config_entry_id == legacy_config_entry.entry_id

        assert (
            er.async_entries_for_config_entry(entity_registry, legacy_config_entry)
            == []
        )
        assert (
            dr.async_entries_for_config_entry(device_registry, legacy_config_entry)
            == []
        )
