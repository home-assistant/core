"""Tests for Fritz!Tools device tracker platform."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_USER_DATA


@pytest.mark.freeze_time(datetime(2026, 8, 18, 20, tzinfo=UTC))
@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "fc_class_mock", "fh_class_mock"
)
async def test_device_tracker_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of Fritz!Tools device_tracker."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fritz.PLATFORMS", [Platform.DEVICE_TRACKER]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("fc_class_mock", "fh_class_mock")
async def test_device_tracker_keeps_existing_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an existing device tracker keeps its entity ID and unique ID."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    # Registered by the integration when it still named the tracker itself
    existing = entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        "AA:BB:CC:00:11:22_tracker",
        config_entry=entry,
        has_entity_name=True,
        object_id_base="old-printer",
        original_name="old-printer",
    )
    assert existing.entity_id == "device_tracker.old_printer"

    with patch("homeassistant.components.fritz.PLATFORMS", [Platform.DEVICE_TRACKER]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    entity_entry = entity_registry.async_get("device_tracker.old_printer")
    assert entity_entry is not None
    assert entity_entry.id == existing.id
    assert entity_entry.unique_id == "AA:BB:CC:00:11:22_tracker"
    assert entity_entry.device_id is not None
    assert entity_registry.async_get("device_tracker.printer") is None
    state = hass.states.get("device_tracker.old_printer")
    assert state is not None
    assert state.attributes["friendly_name"] == "printer"
