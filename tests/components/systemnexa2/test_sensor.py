"""Test the System Nexa 2 sensor platform."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    mock_config_entry.add_to_hass(hass)

    # Only load the sensor platform for snapshot testing
    with patch(
        "homeassistant.components.systemnexa2.PLATFORMS",
        [Platform.SENSOR],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        entity = entity_registry.entities.get(
            "sensor.outdoor_smart_plug_signal_strength"
        )
        assert entity is not None
        entity_registry.async_update_entity(entity.entity_id, disabled_by=None)
        await hass.async_block_till_done()
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
        )

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )
