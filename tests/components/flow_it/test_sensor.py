"""Test Flow-it sensor platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.flow_it.coordinator import FlowItCoordinator
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

INDOOR_AIR_QUALITY_ENTITY_ID = "sensor.001122334455_indoor_air_quality"
INDOOR_AIR_TEMPERATURE_ENTITY_ID = "sensor.001122334455_indoor_air_temperature"


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor platform setup and entity registry."""
    with patch("homeassistant.components.flow_it.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_none_values(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor state when values are None."""
    mock_flow_it.return_value.state.data.mode.temperatureIn = None
    mock_flow_it.return_value.state.data.mode.temperatureOut = None
    mock_flow_it.return_value.state.data.mode.humidityIn = None
    mock_flow_it.return_value.state.data.mode.humidityOut = None
    mock_flow_it.return_value.state.data.mode.pressureIn = None
    mock_flow_it.return_value.state.data.mode.pressureOut = None

    with patch("homeassistant.components.flow_it.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    for entity_id in (
        INDOOR_AIR_TEMPERATURE_ENTITY_ID,
        "sensor.001122334455_outdoor_air_temperature",
        "sensor.001122334455_indoor_air_humidity",
        "sensor.001122334455_outdoor_air_humidity",
        "sensor.001122334455_indoor_air_pressure",
        "sensor.001122334455_outdoor_air_pressure",
    ):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNKNOWN


async def test_sensor_update(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor state updates via coordinator."""
    with patch("homeassistant.components.flow_it.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(INDOOR_AIR_QUALITY_ENTITY_ID)
    assert state
    assert state.state == "100"

    mock_flow_it.return_value.state.data.mode.iaq = 250
    coordinator: FlowItCoordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(INDOOR_AIR_QUALITY_ENTITY_ID)
    assert state
    assert state.state == "250"
