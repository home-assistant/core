"""Test homee sensors."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homee.const import (
    OPEN_CLOSE_MAP,
    OPEN_CLOSE_MAP_REVERSED,
    WINDOW_MAP,
    WINDOW_MAP_REVERSED,
)
from homeassistant.const import LIGHT_LUX
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_update_attribute_value, build_mock_node, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_up_down_values(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test values for up/down sensor."""
    mock_homee.nodes = [build_mock_node("sensors.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_multisensor_state").state == OPEN_CLOSE_MAP[0]

    attribute = mock_homee.nodes[0].attributes[27]
    for i in range(1, 5):
        await async_update_attribute_value(hass, attribute, i)
        assert (
            hass.states.get("sensor.test_multisensor_state").state == OPEN_CLOSE_MAP[i]
        )

    # Test reversed up/down sensor
    attribute.is_reversed = True
    for i in range(5):
        await async_update_attribute_value(hass, attribute, i)
        assert (
            hass.states.get("sensor.test_multisensor_state").state
            == OPEN_CLOSE_MAP_REVERSED[i]
        )


async def test_window_position(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test values for window handle position."""
    mock_homee.nodes = [build_mock_node("sensors.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("sensor.test_multisensor_window_position").state
        == WINDOW_MAP[0]
    )

    attribute = mock_homee.nodes[0].attributes[32]
    for i in range(1, 3):
        await async_update_attribute_value(hass, attribute, i)
        assert (
            hass.states.get("sensor.test_multisensor_window_position").state
            == WINDOW_MAP[i]
        )

    # Test reversed window handle.
    attribute.is_reversed = True
    for i in range(3):
        await async_update_attribute_value(hass, attribute, i)
        assert (
            hass.states.get("sensor.test_multisensor_window_position").state
            == WINDOW_MAP_REVERSED[i]
        )


async def test_brightness_sensor(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test brightness sensor's lx & klx units and naming of multi-instance sensors."""
    mock_homee.nodes = [build_mock_node("sensors.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    sensor_state = hass.states.get("sensor.test_multisensor_illuminance_1")
    assert sensor_state.state == "175.0"
    assert sensor_state.attributes["unit_of_measurement"] == LIGHT_LUX
    assert sensor_state.attributes["friendly_name"] == "Test MultiSensor Illuminance 1"

    # Sensor with Homee unit klx
    sensor_state = hass.states.get("sensor.test_multisensor_illuminance_2")
    assert sensor_state.state == "7000.0"
    assert sensor_state.attributes["unit_of_measurement"] == LIGHT_LUX
    assert sensor_state.attributes["friendly_name"] == "Test MultiSensor Illuminance 2"


async def test_sensor_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the multisensor snapshot."""
    mock_homee.nodes = [build_mock_node("sensors.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)
    entity_registry.async_update_entity(
        "sensor.test_multisensor_node_state", disabled_by=None
    )
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
