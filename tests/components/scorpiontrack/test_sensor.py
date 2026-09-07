"""Test the ScorpionTrack sensor platform."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyscorpiontrack import ScorpionTrackShare
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.scorpiontrack.const import DEFAULT_SCAN_INTERVAL
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    Platform,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "sensor.ab12_cde_speed"


async def test_speed_sensor_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test the speed sensor uses the coordinator snapshot."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert float(state.state) == pytest.approx(48.3 * 0.621371192237334)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfSpeed.MILES_PER_HOUR
    assert ATTR_LATITUDE not in state.attributes
    assert ATTR_LONGITUDE not in state.attributes
    mock_scorpiontrack_client.async_get_share.assert_awaited_once_with()


async def test_speed_sensor_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the speed sensor entity and state attributes."""
    with patch("homeassistant.components.scorpiontrack.PLATFORMS", (Platform.SENSOR,)):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_speed_sensor_metric_display(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test a metric share suggests kilometres per hour."""
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, distance_units="kilometres"
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "48.3"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfSpeed.KILOMETERS_PER_HOUR


@pytest.mark.parametrize(
    ("speed_kmh", "expected_state"),
    [
        pytest.param(0.0, "0.0", id="zero"),
        pytest.param(None, STATE_UNAVAILABLE, id="missing"),
    ],
)
async def test_speed_sensor_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    speed_kmh: float | None,
    expected_state: str,
) -> None:
    """Test zero is valid and missing speed is unavailable."""
    vehicle = mock_share.vehicles[0]
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share,
        vehicles=(
            replace(
                vehicle,
                position=replace(vehicle.position, speed_kmh=speed_kmh),
            ),
        ),
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


async def test_removed_vehicle_makes_speed_sensor_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test a speed sensor becomes unavailable if its vehicle leaves the share."""
    await setup_integration(hass, mock_config_entry)

    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=()
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_speed_sensor_uses_existing_vehicle_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the speed sensor shares the vehicle device with the tracker."""
    await setup_integration(hass, mock_config_entry)

    speed_entry = entity_registry.async_get(ENTITY_ID)
    tracker_entry = entity_registry.async_get("device_tracker.ab12_cde")
    assert speed_entry is not None
    assert tracker_entry is not None
    assert speed_entry.device_id == tracker_entry.device_id
    assert speed_entry.device_id is not None

    device = device_registry.async_get(speed_entry.device_id)
    assert device is not None
    assert device.identifiers == {("scorpiontrack", "101_1")}
