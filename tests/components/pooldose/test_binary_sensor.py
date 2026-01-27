"""Test the PoolDose binary sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pooldose.request_status import RequestStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_binary_sensors(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Pooldose binary sensors."""
    with patch("homeassistant.components.pooldose.PLATFORMS", [Platform.BINARY_SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("exception", [TimeoutError, ConnectionError, OSError])
async def test_exception_raising(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Pooldose binary sensors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.pool_device_recirculation").state == STATE_ON

    mock_pooldose_client.instant_values_structured.side_effect = exception

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.pool_device_recirculation").state
        == STATE_UNAVAILABLE
    )


async def test_no_data(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Pooldose binary sensors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.pool_device_recirculation").state == STATE_ON

    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.SUCCESS,
        None,
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.pool_device_recirculation").state
        == STATE_UNAVAILABLE
    )


async def test_binary_sensor_entity_unavailable_no_coordinator_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor entity becomes unavailable when coordinator has no data."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify initial working state
    pump_state = hass.states.get("binary_sensor.pool_device_recirculation")
    assert pump_state.state == STATE_ON

    # Set coordinator data to None by making API return empty
    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.HOST_UNREACHABLE,
        None,
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check binary sensor becomes unavailable
    pump_state = hass.states.get("binary_sensor.pool_device_recirculation")
    assert pump_state.state == STATE_UNAVAILABLE


async def test_binary_sensor_state_changes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor state changes."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify initial states
    pump_state = hass.states.get("binary_sensor.pool_device_recirculation")
    assert pump_state.state == STATE_ON

    ph_level_state = hass.states.get("binary_sensor.pool_device_ph_tank_level")
    assert ph_level_state.state == STATE_OFF

    # Update data with changed values
    current_data = mock_pooldose_client.instant_values_structured.return_value[1]
    updated_data = current_data.copy()
    updated_data["binary_sensor"]["pump_alarm"]["value"] = False
    updated_data["binary_sensor"]["ph_level_alarm"]["value"] = True

    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.SUCCESS,
        updated_data,
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check states have changed
    pump_state = hass.states.get("binary_sensor.pool_device_recirculation")
    assert pump_state.state == STATE_OFF

    ph_level_state = hass.states.get("binary_sensor.pool_device_ph_tank_level")
    assert ph_level_state.state == STATE_ON


async def test_binary_sensor_missing_from_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor becomes unavailable when missing from coordinator data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify initial working state
    flow_alarm_state = hass.states.get("binary_sensor.pool_device_flow_rate")
    assert flow_alarm_state.state == STATE_OFF

    # Update data with missing sensor
    current_data = mock_pooldose_client.instant_values_structured.return_value[1]
    updated_data = current_data.copy()
    del updated_data["binary_sensor"]["flow_rate_alarm"]

    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.SUCCESS,
        updated_data,
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check sensor becomes unavailable when not in coordinator data
    flow_alarm_state = hass.states.get("binary_sensor.pool_device_flow_rate")
    assert flow_alarm_state.state == STATE_UNAVAILABLE
