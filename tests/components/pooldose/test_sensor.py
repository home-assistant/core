"""Test the PoolDose sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pooldose.request_status import RequestStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    Platform,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_sensors(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Pooldose sensors."""
    with patch("homeassistant.components.pooldose.PLATFORMS", [Platform.SENSOR]):
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
    """Test the Pooldose sensors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.pool_device_ph").state == "6.8"

    mock_pooldose_client.instant_values_structured.side_effect = exception

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.pool_device_ph").state == STATE_UNAVAILABLE


async def test_no_data(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Pooldose sensors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.pool_device_ph").state == "6.8"

    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.SUCCESS,
        None,
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.pool_device_ph").state == STATE_UNAVAILABLE


async def test_ph_sensor_dynamic_unit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test pH sensor unit behavior - pH should not have unit_of_measurement."""
    # Mock pH data with custom unit (should be ignored for pH sensor)
    current_data = mock_pooldose_client.instant_values_structured.return_value[1]
    updated_data = current_data.copy()
    updated_data["sensor"]["ph"]["unit"] = "pH units"

    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.SUCCESS,
        updated_data,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # pH sensor should not have unit_of_measurement (device class pH)
    ph_state = hass.states.get("sensor.pool_device_ph")
    assert ATTR_UNIT_OF_MEASUREMENT not in ph_state.attributes


async def test_sensor_entity_unavailable_no_coordinator_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor entity becomes unavailable when coordinator has no data."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify initial working state
    temp_state = hass.states.get("sensor.pool_device_temperature")
    assert temp_state.state == "25"

    # Set coordinator data to None by making API return empty
    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.HOST_UNREACHABLE,
        None,
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check sensor becomes unavailable
    temp_state = hass.states.get("sensor.pool_device_temperature")
    assert temp_state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_sensor_unit_fallback_to_description(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test sensor falls back to entity description unit when no dynamic unit."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Test ORP sensor - should use static unit from entity description
    orp_state = hass.states.get("sensor.pool_device_orp")
    assert orp_state is not None
    assert (
        orp_state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == UnitOfElectricPotential.MILLIVOLT
    )
    assert orp_state.state == "718"

    # Test pH sensor - should have no unit (None in description)
    ph_state = hass.states.get("sensor.pool_device_ph")
    assert ph_state is not None
    assert ATTR_UNIT_OF_MEASUREMENT not in ph_state.attributes
    assert ph_state.state == "6.8"
