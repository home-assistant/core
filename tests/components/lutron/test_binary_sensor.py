"""Test Lutron binary sensor platform."""

from unittest.mock import MagicMock, patch

from pylutron import OccupancyGroup
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def setup_platforms():
    """Patch PLATFORMS for all tests in this file."""
    with patch("homeassistant.components.lutron.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


async def test_binary_sensor_setup(
    hass: HomeAssistant,
    mock_lutron: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor setup."""
    mock_config_entry.add_to_hass(hass)

    occ_group = mock_lutron.areas[0].occupancy_group
    occ_group.state = OccupancyGroup.State.VACANT

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_binary_sensor_update(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test binary sensor update."""
    mock_config_entry.add_to_hass(hass)

    occ_group = mock_lutron.areas[0].occupancy_group
    occ_group.state = OccupancyGroup.State.VACANT

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "binary_sensor.test_occupancy_occupancy"
    assert hass.states.get(entity_id).state == STATE_OFF

    # Simulate update
    occ_group.state = OccupancyGroup.State.OCCUPIED
    callback = occ_group.subscribe.call_args[0][0]
    callback(occ_group, None, None, None)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON
