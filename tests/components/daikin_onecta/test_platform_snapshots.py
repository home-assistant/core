"""Snapshot tests for each Daikin Onecta entity platform."""

from datetime import UTC, datetime
from pathlib import Path

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.syrupy import HomeAssistantSnapshotExtension
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.single_file import SingleFileAmberSnapshotExtension
from syrupy.location import PyTestLocation

from homeassistant.components.daikin_onecta import PLATFORMS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .platform_helpers import _async_setup_fixture

FIXTURES = (
    "altherma",
    "altherma3m",
    "altherma_boost",
    "altherma_firmwareupdate",
    "altherma_schedule",
    "climate_fixedfanmode",
    "climate_floorheatingairflow",
    "dry",
    "dry2",
    "dx4_firmwareavailable",
    "fanmode",
    "gas",
    "holidaymode",
    "homehub",
    "mc80z",
    "minimal_data",
    "nomodel_id",
    "offlinedevice",
    "skyair",
    "schedule",
    "ururu",
)


class SingleFileHomeAssistantSnapshotExtension(
    HomeAssistantSnapshotExtension, SingleFileAmberSnapshotExtension
):
    """Store platform snapshots in separate files."""

    @classmethod
    def dirname(cls, *, test_location: PyTestLocation) -> str:
        """Return the per-test snapshot directory."""
        return str(
            Path(test_location.filepath).parent / "snapshots" / test_location.basename
        )


@pytest.mark.parametrize("fixture", FIXTURES)
async def test_platform_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    fixture: str,
) -> None:
    """Snapshot the entities created by each platform for every response fixture."""
    freezer.move_to(datetime(2026, 10, 15, 12, tzinfo=UTC))
    await _async_setup_fixture(hass, config_entry, fixture)

    entries_by_platform = {platform: {} for platform in PLATFORMS}
    for entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        entries_by_platform[entry.domain][entry.entity_id] = {
            "unique_id": entry.unique_id,
            "disabled_by": entry.disabled_by,
            "state": hass.states.get(entry.entity_id),
        }

    for platform, entities in entries_by_platform.items():
        assert entities == snapshot(
            name=f"{fixture}_{platform}",
            extension_class=SingleFileHomeAssistantSnapshotExtension,
        )
