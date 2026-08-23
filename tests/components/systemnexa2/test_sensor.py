"""Test the System Nexa 2 sensor platform."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_system_nexa_2_device")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
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
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )
