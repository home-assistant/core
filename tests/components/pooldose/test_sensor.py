"""Test the PoolDose sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pooldose.request_status import RequestStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
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


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_ph_sensor_dynamic_unit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client,
) -> None:
    """Test pH sensor unit behavior - pH should not have unit_of_measurement."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Mock pH data with custom unit (should be ignored for pH sensor)
    coordinator = mock_config_entry.runtime_data
    updated_data = coordinator.data.copy()
    updated_data["sensor"]["ph"]["unit"] = "pH units"

    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.SUCCESS,
        updated_data,
    )

    # Trigger refresh by reloading the integration
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # pH sensor should not have unit_of_measurement (device class pH)
    ph_state = hass.states.get("sensor.pool_device_ph")
    assert "unit_of_measurement" not in ph_state.attributes


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
async def test_temperature_sensor_unit_from_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test temperature sensor correctly reads unit from API data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify sensor correctly uses unit from API data
    temp_state = hass.states.get("sensor.pool_device_temperature")
    assert temp_state is not None
    assert temp_state.state == "25"
    assert temp_state.attributes["unit_of_measurement"] == "°C"


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_flow_rate_sensor_unit_from_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test flow rate sensor gets unit from API data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify sensor uses unit from fixture data
    flow_state = hass.states.get("sensor.pool_device_flow_rate")
    assert flow_state is not None
    assert flow_state.attributes["unit_of_measurement"] == "L/s"
    assert flow_state.state == "150"


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
    assert orp_state.attributes["unit_of_measurement"] == "mV"
    assert orp_state.state == "718"

    # Test pH sensor - should have no unit (None in description)
    ph_state = hass.states.get("sensor.pool_device_ph")
    assert ph_state is not None
    assert "unit_of_measurement" not in ph_state.attributes
    assert ph_state.state == "6.8"


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_sensor_no_data_returns_none_unit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test sensor returns None unit when no data available."""
    # Mock API response with missing temperature and flow_rate data
    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.SUCCESS,
        {"sensor": {}, "binary_sensor": {}, "number": {}, "switch": {}, "select": {}},
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify no temperature entities are created when no data
    temp_state = hass.states.get("sensor.pool_device_temperature")
    # Entity may be created but should be unavailable or have no unit
    if temp_state:
        assert temp_state.state == "unavailable"


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_device_unit_change_behavior(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test what happens when device changes its unit setting."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Simulate device unit change - get current data and modify it
    coordinator = mock_config_entry.runtime_data
    changed_data = coordinator.data.copy()
    changed_data["sensor"]["temperature"]["unit"] = "°F"
    changed_data["sensor"]["temperature"]["value"] = 77.0  # 25°C in °F
    changed_data["sensor"]["flow_rate"]["unit"] = "L/min"
    changed_data["sensor"]["flow_rate"]["value"] = 9000.0

    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.SUCCESS,
        changed_data,
    )

    # Trigger coordinator refresh to simulate device unit change
    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check entity states after refresh
    temp_state_after = hass.states.get("sensor.pool_device_temperature")
    flow_state_after = hass.states.get("sensor.pool_device_flow_rate")

    assert temp_state_after is not None
    assert flow_state_after is not None

    # Temperature remains 25°C due to HA automatic conversion °F to °C
    assert float(temp_state_after.state) == 25.0

    # Flow rate changes both value and unit
    assert float(flow_state_after.state) == 9000.0
    assert flow_state_after.attributes["unit_of_measurement"] == "L/min"
