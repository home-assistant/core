"""Tests the lifx migration."""

from datetime import timedelta

from homeassistant import setup
from homeassistant.components.lifx import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry
import homeassistant.util.dt as dt_util

from . import (
    IP_ADDRESS,
    LABEL,
    MAC_ADDRESS,
    SERIAL,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_migration_device_online_end_to_end(
    hass: HomeAssistant, device_reg: DeviceRegistry, entity_reg: EntityRegistry
):
    """Test migration from single config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, title="LEGACY", data={}, unique_id=DOMAIN
    )
    config_entry.add_to_hass(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, SERIAL)},
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
        name=LABEL,
    )
    light_entity_reg = entity_reg.async_get_or_create(
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
        assert er.async_entries_for_config_entry(entity_reg, config_entry) == []

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=20))
        await hass.async_block_till_done()

        legacy_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == DOMAIN:
                legacy_entry = entry
                break

        assert legacy_entry is None


async def test_migration_device_online_end_to_end_after_downgrade(
    hass: HomeAssistant, device_reg: DeviceRegistry, entity_reg: EntityRegistry
):
    """Test migration from single config entry can happen again after a downgrade."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, title="LEGACY", data={}, unique_id=DOMAIN
    )
    config_entry.add_to_hass(hass)

    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, SERIAL)},
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
        name=LABEL,
    )
    light_entity_reg = entity_reg.async_get_or_create(
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
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=20))
        await hass.async_block_till_done()

        assert device.config_entries == {config_entry.entry_id}
        assert light_entity_reg.config_entry_id == config_entry.entry_id
        assert er.async_entries_for_config_entry(entity_reg, config_entry) == []

        legacy_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == DOMAIN:
                legacy_entry = entry
                break

        assert legacy_entry is None


async def test_migration_device_online_end_to_end_ignores_other_devices(
    hass: HomeAssistant, device_reg: DeviceRegistry, entity_reg: EntityRegistry
):
    """Test migration from single config entry."""
    legacy_config_entry = MockConfigEntry(
        domain=DOMAIN, title="LEGACY", data={}, unique_id=DOMAIN
    )
    legacy_config_entry.add_to_hass(hass)

    other_domain_config_entry = MockConfigEntry(
        domain="other_domain", data={}, unique_id="other_domain"
    )
    other_domain_config_entry.add_to_hass(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=legacy_config_entry.entry_id,
        identifiers={(DOMAIN, SERIAL)},
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
        name=LABEL,
    )
    other_device = device_reg.async_get_or_create(
        config_entry_id=other_domain_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "556655665566")},
        name=LABEL,
    )
    light_entity_reg = entity_reg.async_get_or_create(
        config_entry=legacy_config_entry,
        platform=DOMAIN,
        domain="light",
        unique_id=SERIAL,
        original_name=LABEL,
        device_id=device.id,
    )
    ignored_entity_reg = entity_reg.async_get_or_create(
        config_entry=other_domain_config_entry,
        platform=DOMAIN,
        domain="sensor",
        unique_id="00:00:00:00:00:00_sensor",
        original_name=LABEL,
        device_id=device.id,
    )
    garbage_entity_reg = entity_reg.async_get_or_create(
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

        assert er.async_entries_for_config_entry(entity_reg, legacy_config_entry) == []
        assert dr.async_entries_for_config_entry(device_reg, legacy_config_entry) == []
