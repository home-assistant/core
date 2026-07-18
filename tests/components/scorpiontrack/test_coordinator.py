"""Test the ScorpionTrack coordinator."""

from dataclasses import replace
from datetime import timedelta
from typing import cast
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyscorpiontrack import ScorpionTrackConnectionError, ScorpionTrackShare
import pytest

from homeassistant.components.scorpiontrack.const import (
    ACTIVE_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)
from homeassistant.components.scorpiontrack.coordinator import ScorpionTrackCoordinator
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


def _get_state(hass: HomeAssistant, entity_id: str) -> State:
    """Return an entity state that must exist."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_active_refresh_updates_all_vehicle_entities(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test one active refresh updates tracker and telemetry entities."""
    await setup_integration(hass, mock_config_entry)
    mock_scorpiontrack_client.async_get_share.assert_awaited_once_with()

    initial_timestamp = mock_share.vehicles[0].position.timestamp
    assert initial_timestamp is not None
    updated_timestamp = (initial_timestamp + ACTIVE_SCAN_INTERVAL).replace(
        microsecond=0
    )
    updated_position = replace(
        mock_share.vehicles[0].position,
        latitude=52.52,
        longitude=13.405,
        timestamp=updated_timestamp,
        speed_kmh=80.0,
        ignition=False,
        bearing=270.0,
    )
    updated_share = replace(
        mock_share,
        vehicles=(replace(mock_share.vehicles[0], position=updated_position),),
    )
    mock_scorpiontrack_client.async_get_share.return_value = updated_share

    freezer.tick(ACTIVE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_scorpiontrack_client.async_get_share.await_count == 2
    tracker = _get_state(hass, "device_tracker.ab12_cde")
    assert tracker.attributes[ATTR_LATITUDE] == 52.52
    assert tracker.attributes[ATTR_LONGITUDE] == 13.405
    speed = _get_state(hass, "sensor.ab12_cde_speed")
    assert float(speed.state) == pytest.approx(49.7, abs=0.05)
    assert speed.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfSpeed.MILES_PER_HOUR
    assert float(_get_state(hass, "sensor.ab12_cde_heading").state) == 270.0
    assert (
        _get_state(hass, "sensor.ab12_cde_last_reported").state
        == updated_timestamp.isoformat()
    )
    assert _get_state(hass, "binary_sensor.ab12_cde_ignition").state == STATE_OFF


@pytest.mark.parametrize(
    ("ignition_states", "expected_interval"),
    [
        pytest.param((False,), DEFAULT_SCAN_INTERVAL, id="parked"),
        pytest.param((None,), DEFAULT_SCAN_INTERVAL, id="unknown"),
        pytest.param((False, True), ACTIVE_SCAN_INTERVAL, id="any-active"),
    ],
)
async def test_initial_interval_follows_any_vehicle_ignition(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    ignition_states: tuple[bool | None, ...],
    expected_interval: timedelta,
) -> None:
    """Test the initial interval follows explicit ignition state."""
    vehicles = tuple(
        replace(
            mock_share.vehicles[0],
            id=vehicle_id,
            registration=f"TEST {vehicle_id}",
            position=replace(
                mock_share.vehicles[0].position,
                ignition=ignition,
            ),
        )
        for vehicle_id, ignition in enumerate(ignition_states, start=1)
    )
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=vehicles
    )

    await setup_integration(hass, mock_config_entry)

    coordinator: ScorpionTrackCoordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == expected_interval
    mock_scorpiontrack_client.async_get_share.assert_awaited_once_with()


async def test_activity_requires_explicit_true_ignition(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test speed, status, and a truthy string do not imply activity."""
    position = replace(
        mock_share.vehicles[0].position,
        speed_kmh=80.0,
        ignition=cast(bool | None, "true"),
    )
    vehicle = replace(mock_share.vehicles[0], position=position, status="Moving")
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=(vehicle,)
    )

    await setup_integration(hass, mock_config_entry)

    coordinator: ScorpionTrackCoordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == DEFAULT_SCAN_INTERVAL


async def test_active_share_refreshes_after_fifteen_seconds(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test an active share is scheduled at the active cadence."""
    await setup_integration(hass, mock_config_entry)

    freezer.tick(ACTIVE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_scorpiontrack_client.async_get_share.await_count == 2


async def test_active_share_gets_one_trailing_fast_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test activity provides one final fast refresh after ignition stops."""
    await setup_integration(hass, mock_config_entry)
    coordinator: ScorpionTrackCoordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == ACTIVE_SCAN_INTERVAL

    inactive_vehicle = replace(
        mock_share.vehicles[0],
        position=replace(mock_share.vehicles[0].position, ignition=False),
    )
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=(inactive_vehicle,)
    )

    await coordinator.async_refresh()
    assert coordinator.update_interval == ACTIVE_SCAN_INTERVAL
    await coordinator.async_refresh()
    assert coordinator.update_interval == DEFAULT_SCAN_INTERVAL
    assert mock_scorpiontrack_client.async_get_share.await_count == 3


async def test_inactive_share_remains_on_parked_interval(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test a sustained inactive share remains at the parked cadence."""
    inactive_vehicle = replace(
        mock_share.vehicles[0],
        position=replace(mock_share.vehicles[0].position, ignition=False),
    )
    inactive_share = replace(mock_share, vehicles=(inactive_vehicle,))
    mock_scorpiontrack_client.async_get_share.return_value = inactive_share

    await setup_integration(hass, mock_config_entry)
    coordinator: ScorpionTrackCoordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == DEFAULT_SCAN_INTERVAL

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_scorpiontrack_client.async_get_share.await_count == 2
    assert coordinator.update_interval == DEFAULT_SCAN_INTERVAL


async def test_connection_error_retries_after_parked_interval(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test a failed active refresh retries after sixty seconds."""
    await setup_integration(hass, mock_config_entry)
    coordinator: ScorpionTrackCoordinator = mock_config_entry.runtime_data
    previous_data = coordinator.data

    inactive_vehicle = replace(
        mock_share.vehicles[0],
        position=replace(mock_share.vehicles[0].position, ignition=False),
    )
    inactive_share = replace(mock_share, vehicles=(inactive_vehicle,))
    mock_scorpiontrack_client.async_get_share.side_effect = (
        ScorpionTrackConnectionError("Connection failed"),
        inactive_share,
        inactive_share,
    )

    freezer.tick(ACTIVE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_scorpiontrack_client.async_get_share.await_count == 2
    assert not coordinator.last_update_success
    assert coordinator.data is previous_data
    assert coordinator.vehicles_by_id[1].position.ignition is True
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert (
        coordinator.last_exception.retry_after == DEFAULT_SCAN_INTERVAL.total_seconds()
    )

    freezer.tick(ACTIVE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_scorpiontrack_client.async_get_share.await_count == 2

    freezer.tick(DEFAULT_SCAN_INTERVAL - ACTIVE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_scorpiontrack_client.async_get_share.await_count == 3
    assert coordinator.last_update_success
    assert coordinator.update_interval == ACTIVE_SCAN_INTERVAL

    freezer.tick(ACTIVE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_scorpiontrack_client.async_get_share.await_count == 4
    assert coordinator.update_interval == DEFAULT_SCAN_INTERVAL
