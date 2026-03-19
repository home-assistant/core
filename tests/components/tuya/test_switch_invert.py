"""Test Tuya cover inversion config switches."""

from __future__ import annotations

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya.const import cover_unique_id
from homeassistant.components.tuya.cover import COVERS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import initialize_entry

from tests.common import MockConfigEntry


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SWITCH])
async def test_cover_invert_switches_snapshot(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the local invert-status switches created for Tuya covers."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    invert_entries = sorted(
        (
            entity_entry
            for entity_entry in entity_entries
            if entity_entry.unique_id.endswith("_invert_status")
        ),
        key=lambda entity_entry: entity_entry.entity_id,
    )

    expected_invert_unique_ids = {
        f"{cover_unique_id(device.id, description.key)}_invert_status"
        for device in mock_devices
        if (descriptions := COVERS.get(device.category))
        for description in descriptions
        if description.key in device.function or description.key in device.status_range
    }
    assert {entry.unique_id for entry in invert_entries} == expected_invert_unique_ids

    assert {
        entity_entry.unique_id: {
            "entity_category": entity_entry.entity_category,
            "state": hass.states.get(entity_entry.entity_id).state,
            "translation_key": entity_entry.translation_key,
        }
        for entity_entry in invert_entries
    } == snapshot
