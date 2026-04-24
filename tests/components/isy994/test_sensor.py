"""Test the ISY994 sensor platform."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.isy994.const import UOM_FRIENDLY_NAME
from homeassistant.components.isy994.sensor import (
    ISY_CONTROL_TO_STATE_CLASS,
    UOM_TO_DEVICE_CLASS,
    ISYSensorEntity,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import Platform, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


def test_mappings() -> None:
    """Test that mappings are correctly defined."""
    # Test UOM to Device Class
    assert UOM_TO_DEVICE_CLASS["4"] == SensorDeviceClass.TEMPERATURE
    assert UOM_TO_DEVICE_CLASS["33"] == SensorDeviceClass.ENERGY
    assert UOM_TO_DEVICE_CLASS["143"] == SensorDeviceClass.VOLUME_FLOW_RATE
    assert UOM_TO_DEVICE_CLASS["69"] == SensorDeviceClass.WATER
    assert UOM_TO_DEVICE_CLASS["24"] == SensorDeviceClass.PRECIPITATION_INTENSITY

    # Test UOM to Unit String
    assert UOM_FRIENDLY_NAME["130"] == UnitOfVolumeFlowRate.LITERS_PER_HOUR
    assert UOM_FRIENDLY_NAME["143"] == UnitOfVolumeFlowRate.GALLONS_PER_MINUTE
    assert UOM_FRIENDLY_NAME["144"] == UnitOfVolumeFlowRate.GALLONS_PER_HOUR

    # Test Control to State Class
    assert ISY_CONTROL_TO_STATE_CLASS["TPW"] == SensorStateClass.TOTAL_INCREASING
    assert ISY_CONTROL_TO_STATE_CLASS["CPW"] == SensorStateClass.MEASUREMENT


def test_isy_sensor_entity_properties() -> None:
    """Test ISYSensorEntity property logic."""
    mock_node = MagicMock()
    mock_node.isy.uuid = "12345"
    mock_node.address = "1 2 3 1"
    mock_node.name = "Test Node"
    mock_node.status = 100
    mock_node.uom = "4"  # Celsius
    mock_node.prec = "1"
    mock_node.status_events.subscribe.return_value = MagicMock()

    entity = ISYSensorEntity(mock_node)

    # Should use UOM mapping
    assert entity.device_class == SensorDeviceClass.TEMPERATURE
    assert entity.state_class == SensorStateClass.MEASUREMENT

    # Should respect explicit attribute
    entity._attr_device_class = SensorDeviceClass.HUMIDITY
    assert entity.device_class == SensorDeviceClass.HUMIDITY

    # Test state_class for TOTAL_INCREASING
    mock_node.uom = "33"  # Energy
    entity._attr_device_class = None
    entity._attr_state_class = None
    assert entity.device_class == SensorDeviceClass.ENERGY
    assert entity.state_class == SensorStateClass.TOTAL_INCREASING


async def test_sensor_snapshots(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_isy: MagicMock,
    mock_node: callable,
) -> None:
    """Test sensors with snapshots."""
    mock_config_entry.add_to_hass(hass)

    # Mock some nodes with standardized UOMs from PR 169017
    # Node 1: Liters per Hour
    node1 = mock_node(mock_isy, "22 22 22 1", "Flow Rate LPH", "GenericSensor")
    node1.status = 1000
    node1.uom = "130"
    node1.prec = "1"

    # Node 2: Gallons per Minute
    node2 = mock_node(mock_isy, "22 22 22 2", "Flow Rate GPM", "GenericSensor")
    node2.status = 50
    node2.uom = "143"
    node2.prec = "1"

    # Node 3: Gallons per Hour
    node3 = mock_node(mock_isy, "22 22 22 3", "Flow Rate GPH", "GenericSensor")
    node3.status = 300
    node3.uom = "144"
    node3.prec = "0"

    mock_isy.nodes.__iter__.return_value = [
        ("Sensors/Flow Rate LPH", node1),
        ("Sensors/Flow Rate GPM", node2),
        ("Sensors/Flow Rate GPH", node3),
    ]

    with patch("homeassistant.components.isy994.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Enable disabled entities
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entry in entity_entries:
        if entry.disabled_by:
            entity_registry.async_update_entity(entry.entity_id, disabled_by=None)

    with patch("homeassistant.components.isy994.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
