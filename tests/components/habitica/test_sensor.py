"""Test Habitica sensor platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


@pytest.mark.usefixtures("habitica", "entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    config_entry_with_subentry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Habitica sensor platform."""

    config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_subentry.state is ConfigEntryState.LOADED

    await snapshot_platform(
        hass, entity_registry, snapshot, config_entry_with_subentry.entry_id
    )
