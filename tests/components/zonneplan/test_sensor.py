"""Tests for the Zonneplan sensor platform."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.zonneplan import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.parametrize(
    "frozen_time",
    [
        pytest.param("2026-08-29T08:30:00+00:00", id="prices_published"),
        pytest.param("2026-08-30T00:30:00+00:00", id="prices_incoming"),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    frozen_time: str,
) -> None:
    """Test the sensor entities."""
    with patch(
        "homeassistant.components.zonneplan.PLATFORMS",
        [Platform.SENSOR],
    ):
        freezer.move_to(frozen_time)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
