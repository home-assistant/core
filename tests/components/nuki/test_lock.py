"""Tests for the nuki locks."""

from unittest.mock import patch

import requests_mock
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nuki.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .mock import setup_nuki_integration

from tests.common import snapshot_platform


async def test_locks(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_nuki_requests: requests_mock.Mocker,
) -> None:
    """Test locks."""
    with patch("homeassistant.components.nuki.PLATFORMS", [Platform.LOCK]):
        entry = await init_integration(hass, mock_nuki_requests)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)

    # Unload the config entry after taking a snapshot is required
    # because the integration may cache DNS results or keep
    # references to the original gethostbyname, so unloading
    # ensures the patch is effective for subsequent tests and
    # avoids DNS lookups
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_integer_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_nuki_requests: requests_mock.Mocker,
) -> None:
    """Test legacy integer unique IDs are migrated without replacing entities."""
    entry = await setup_nuki_integration(hass)
    legacy_entry = entity_registry.async_get_or_create(
        Platform.LOCK,
        DOMAIN,
        1,  # type: ignore[arg-type]
        config_entry=entry,
        suggested_object_id="custom_nuki_lock",
    )

    with patch("homeassistant.components.nuki.PLATFORMS", [Platform.LOCK]):
        await init_integration(hass, mock_nuki_requests, entry)

    migrated_entry = entity_registry.async_get(legacy_entry.entity_id)
    assert migrated_entry is not None
    assert migrated_entry.id == legacy_entry.id
    assert migrated_entry.entity_id == "lock.custom_nuki_lock"
    assert migrated_entry.unique_id == "1"
    assert entity_registry.async_get_entity_id(Platform.LOCK, DOMAIN, "1") == (
        legacy_entry.entity_id
    )
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 2

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
