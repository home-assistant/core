"""Test ViCare binary sensors."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "entity_id",
    [
        "burner",
        "circulation_pump",
        "frost_protection",
    ],
)
async def test_binary_sensors(
    hass: HomeAssistant,
    mock_vicare_gas_boiler: MagicMock,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test the ViCare binary sensor."""
    assert hass.states.get(f"binary_sensor.model0_{entity_id}") == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    fixtures: list[Fixture] = [Fixture({"type:boiler"}, "vicare/Vitodens300W.json")]
    with (
        patch(f"{MODULE}.login", return_value=MockPyViCare(fixtures)),
        patch(f"{MODULE}.PLATFORMS", [Platform.BINARY_SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
