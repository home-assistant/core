"""Test the mvglive sensor platform."""

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mvglive.sensor import PLATFORM_SCHEMA
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


def test_platform_schema_accepts_deprecated_directions() -> None:
    """Test PLATFORM_SCHEMA still accepts the deprecated `directions` key."""
    PLATFORM_SCHEMA(
        {
            "platform": "mvglive",
            "nextdeparture": [{"station": "Hauptbahnhof", "directions": "Feldmoching"}],
        }
    )


@pytest.mark.usefixtures("mvg_api")
async def test_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the departures sensor entity."""
    freezer.move_to("2026-08-19 12:00:00+00:00")
    await setup_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
