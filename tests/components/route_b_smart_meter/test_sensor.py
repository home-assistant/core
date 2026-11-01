"""Tests for the Smart Meter B-Route sensor."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
from momonga import MomongaError, MomongaSkScanFailure
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.route_b_smart_meter.const import DEFAULT_SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_route_b_smart_meter_sensor_update(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the BRouteUpdateCoordinator successful behavior."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_route_b_smart_meter_sensor_no_update(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the BRouteUpdateCoordinator when failing."""

    entity_id = (
        "sensor.route_b_smart_meter_"
        "01234567890123456789012345f789_"
        "instantaneous_current_r_phase"
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity.state == "1"

    mock_momonga.return_value.get_instantaneous_current.side_effect = MomongaError
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(entity_id)
    assert entity.state is STATE_UNAVAILABLE


async def test_route_b_smart_meter_sensor_no_data(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors are unknown when the meter reports no data."""
    entity_prefix = "sensor.route_b_smart_meter_01234567890123456789012345f789_"
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = mock_momonga.return_value
    client.get_instantaneous_current.return_value = {
        "r phase current": None,
        "t phase current": 2,
    }
    client.get_instantaneous_power.return_value = None
    client.get_measured_cumulative_energy.return_value = None
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for key in (
        "instantaneous_current_r_phase",
        "instantaneous_power",
        "total_consumption",
    ):
        assert hass.states.get(f"{entity_prefix}{key}").state == STATE_UNKNOWN
    assert hass.states.get(f"{entity_prefix}instantaneous_current_t_phase").state == "2"


async def test_route_b_smart_meter_sensor_reopen_closed_session(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a session left closed is reopened on the next update."""
    entity_id = (
        "sensor.route_b_smart_meter_01234567890123456789012345f789_instantaneous_power"
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = mock_momonga.return_value
    client.is_open = False
    client.reopen.side_effect = MomongaSkScanFailure
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state is STATE_UNAVAILABLE
    client.get_instantaneous_power.assert_called_once()

    def reopen() -> None:
        client.is_open = True

    client.reopen.side_effect = reopen
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "3"
    assert client.reopen.call_count == 2
