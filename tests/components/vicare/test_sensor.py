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
@pytest.mark.parametrize(
    ("fixture_type", "fixture_data"),
    [
        ("type:boiler", "vicare/Vitodens300W.json"),
        ("type:heatpump", "vicare/Vitocal250A.json"),
        ("type:ventilation", "vicare/ViAir300F.json"),
        ("type:ess", "vicare/VitoChargeVX3.json"),
        (None, "vicare/VitoValor.json"),
    ],
)
async def test_all_entities(
    hass: HomeAssistant,
    fixture_type: str,
    fixture_data: str,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    fixtures: list[Fixture] = [
        Fixture({fixture_type}, fixture_data),
        Fixture({"type:climateSensor"}, "vicare/RoomSensor1.json"),
        Fixture({"type:climateSensor"}, "vicare/RoomSensor2.json"),
        Fixture({"type:radiator"}, "vicare/ZigbeeTRV.json"),
        Fixture({"type:repeater"}, "vicare/ZigbeeRepeater.json"),
        Fixture({"type:fhtMain"}, "vicare/FHTMain.json"),
        Fixture({"type:fhtChannel"}, "vicare/FHTChannel.json"),
    ]
    with (
        patch(f"{MODULE}.login", return_value=MockPyViCare(fixtures)),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
