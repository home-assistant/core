"""Test the Google Air Quality media source."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("setup_integration_and_subentry")
async def test_sensor_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_and_subentry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test of the sensors."""
    await hass.async_block_till_done()
    assert config_and_subentry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.google_air_quality.PLATFORMS",
        [Platform.SENSOR],
    ):
        await snapshot_platform(
            hass, entity_registry, snapshot, config_and_subentry.entry_id
        )
