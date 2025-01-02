"""Test ViCare sensor entity."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    fixtures: list[Fixture] = [
        Fixture({"type:boiler"}, "vicare/Vitodens300W.json"),
    ]
    with (
        patch(f"{MODULE}.login", return_value=MockPyViCare(fixtures)),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_room_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    fixtures: list[Fixture] = [
        Fixture({"type:climateSensor"}, "vicare/RoomSensor1.json"),
        Fixture({"type:climateSensor"}, "vicare/RoomSensor2.json"),
    ]
    with (
        patch(f"{MODULE}.login", return_value=MockPyViCare(fixtures)),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
