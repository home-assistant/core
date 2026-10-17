"""Test the flume sensor."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def platforms_fixture():
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.flume.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("access_token", "device_list")
async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensors."""
    hass.config.units = US_CUSTOMARY_SYSTEM

    flume_values = {
        "current_interval": 1.23,
        "month_to_date": 100.1,
        "week_to_date": 50.5,
        "today": 10.2,
        "last_60_min": 5.5,
        "last_24_hrs": 20.4,
        "last_30_days": 150.8,
    }

    with patch("homeassistant.components.flume.sensor.FlumeData") as mock_flume_data:
        mock_flume_data.return_value.values = flume_values

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
