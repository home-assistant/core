"""Test the ISY994 sensor platform."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def mock_sensor_platform():
    """Mock the platforms to only include sensor."""
    with patch("homeassistant.components.isy994.PLATFORMS", [Platform.SENSOR]):
        yield


async def test_sensor_snapshots(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
) -> None:
    """Test sensors with snapshots."""
    mock_config_entry.add_to_hass(hass)

    # Mock nodes covering various UOMs and device classes
    nodes = []

    # Standardized UOMs
    # Node 1: Liters per Hour
    node1 = mock_node(mock_isy, "22 22 22 1", "Flow Rate LPH", "GenericSensor")
    node1.status = 1000
    node1.uom = "130"
    node1.prec = "1"
    nodes.append(("Sensors/Flow Rate LPH", node1))

    # Node 2: Gallons per Minute
    node2 = mock_node(mock_isy, "22 22 22 2", "Flow Rate GPM", "GenericSensor")
    node2.status = 50
    node2.uom = "143"
    node2.prec = "1"
    nodes.append(("Sensors/Flow Rate GPM", node2))

    # Node 3: Gallons per Hour
    node3 = mock_node(mock_isy, "22 22 22 3", "Flow Rate GPH", "GenericSensor")
    node3.status = 300
    node3.uom = "144"
    node3.prec = "0"
    nodes.append(("Sensors/Flow Rate GPH", node3))

    # Node 9: Gallons per Second (142) - Should have NO device_class due to guard
    node9 = mock_node(mock_isy, "22 22 22 9", "Flow Rate GPS", "GenericSensor")
    node9.status = 1
    node9.uom = "142"
    node9.prec = "1"
    nodes.append(("Sensors/Flow Rate GPS", node9))

    # Node 10: Gallons per Second (142) in ISYv4 list form - guard must still apply
    node10 = mock_node(mock_isy, "22 22 22 10", "Flow Rate GPS List", "GenericSensor")
    node10.status = 2
    node10.uom = ["142"]
    node10.prec = "1"
    nodes.append(("Sensors/Flow Rate GPS List", node10))

    # Other UOMs from test_mappings
    # Temperature (4)
    node4 = mock_node(mock_isy, "22 22 22 4", "Temperature", "GenericSensor")
    node4.status = 215
    node4.uom = "4"
    node4.prec = "1"
    nodes.append(("Sensors/Temperature", node4))

    # Energy (33) - TOTAL_INCREASING
    node5 = mock_node(mock_isy, "22 22 22 5", "Energy", "GenericSensor")
    node5.status = 123456
    node5.uom = "33"
    node5.prec = "0"
    nodes.append(("Sensors/Energy", node5))

    # Precipitation Intensity (24)
    node6 = mock_node(mock_isy, "22 22 22 6", "Rain Rate", "GenericSensor")
    node6.status = 12
    node6.uom = "24"
    node6.prec = "1"
    nodes.append(("Sensors/Rain Rate", node6))

    # Water (69)
    node7 = mock_node(mock_isy, "22 22 22 7", "Water Meter", "GenericSensor")
    node7.status = 9876
    node7.uom = "69"
    node7.prec = "0"
    nodes.append(("Sensors/Water Meter", node7))

    # Aux Properties (TPW, CPW)
    node8 = mock_node(mock_isy, "22 22 22 8", "Power Node", "GenericSensor")
    node8.status = 0
    node8.uom = "73"  # Watts
    node8.aux_properties = {
        "TPW": MagicMock(value=50000, uom="33", prec="0"),  # Total Power (Energy)
        "CPW": MagicMock(value=250, uom="73", prec="0"),  # Current Power
    }
    nodes.append(("Sensors/Power Node", node8))

    # Aux FLOW with ISYv4 list-form UOM 142 (gal/s) - guard must clear
    # device_class without raising TypeError on the unhashable list.
    node11 = mock_node(mock_isy, "22 22 22 11", "Flow Aux List", "GenericSensor")
    node11.status = 0
    node11.uom = "73"
    node11.aux_properties = {
        "FLOW": MagicMock(value=1, uom=["142"], prec="1"),
    }
    nodes.append(("Sensors/Flow Aux List", node11))

    mock_isy.nodes.__iter__.return_value = nodes

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Enable disabled entities (like aux sensors)
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entry in entity_entries:
        if entry.disabled_by:
            entity_registry.async_update_entity(entry.entity_id, disabled_by=None)

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
