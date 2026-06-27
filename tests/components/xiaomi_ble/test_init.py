"""Tests for the Xiaomi BLE integration __init__ module."""

from __future__ import annotations

from homeassistant.components.xiaomi_ble.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

S400_ADDRESS = "04:AE:47:67:C6:7C"
S400_MODEL = "MJTZC01YM"


async def _async_setup_legacy_impedance_entity(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    *,
    model: str = S400_MODEL,
) -> str:
    """Create a device + legacy 'impedance' entity, simulating a pre-migration install."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("bluetooth", S400_ADDRESS)},
        model=model,
        name="Body Composition Scale C67C",
    )

    entity_registry = er.async_get(hass)
    entry_entity = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{S400_ADDRESS}-impedance",
        config_entry=entry,
        device_id=device_entry.id,
        original_name="Impedance",
    )
    return entry_entity.entity_id


async def test_migrate_s400_legacy_impedance_disabled(hass: HomeAssistant) -> None:
    """Test that the legacy generic impedance entity is disabled for an S400."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=S400_ADDRESS)
    entry.add_to_hass(hass)

    entity_id = await _async_setup_legacy_impedance_entity(hass, entry)

    entity_registry = er.async_get(hass)
    before = entity_registry.async_get(entity_id)
    assert before is not None
    assert before.disabled_by is None

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get(entity_id)
    assert after is not None
    assert after.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_s400_legacy_impedance_already_disabled(
    hass: HomeAssistant,
) -> None:
    """Test the migration is a no-op if the legacy entity is already disabled."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=S400_ADDRESS)
    entry.add_to_hass(hass)

    entity_id = await _async_setup_legacy_impedance_entity(hass, entry)

    entity_registry = er.async_get(hass)
    entity_registry.async_update_entity(
        entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get(entity_id)
    assert after is not None
    # The migration must not override a disable reason set by someone else
    # (e.g. the user manually disabling it) with its own.
    assert after.disabled_by is er.RegistryEntryDisabler.USER

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_skipped_for_non_s400_device(hass: HomeAssistant) -> None:
    """Test the legacy impedance entity is left untouched for non-S400 scales."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=S400_ADDRESS)
    entry.add_to_hass(hass)

    entity_id = await _async_setup_legacy_impedance_entity(
        hass, entry, model="XMTZC02HM/XMTZC05HM/NUN4049CN"
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    after = entity_registry.async_get(entity_id)
    assert after is not None
    assert after.disabled_by is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_skipped_when_no_legacy_entity(hass: HomeAssistant) -> None:
    """Test the migration does nothing when there is no legacy entity to migrate."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=S400_ADDRESS)
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("bluetooth", S400_ADDRESS)},
        model=S400_MODEL,
        name="Body Composition Scale C67C",
    )

    # No legacy "impedance" entity registered: should not raise.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_skipped_when_no_device_entry(hass: HomeAssistant) -> None:
    """Test the migration does nothing when the device is not yet known."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=S400_ADDRESS)
    entry.add_to_hass(hass)

    # No device registered at all for this address: should not raise.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
