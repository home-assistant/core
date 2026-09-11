"""Test the ScorpionTrack sensor platform."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyscorpiontrack import ScorpionTrackConnectionError, ScorpionTrackShare
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.scorpiontrack.const import DEFAULT_SCAN_INTERVAL
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "sensor.ab12_cde_speed"
LAST_REPORTED_ENTITY_ID = "sensor.ab12_cde_last_reported"
HEADING_ENTITY_ID = "sensor.ab12_cde_heading"


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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.freeze_time("2026-08-11 12:00:00+00:00")
async def test_sensor_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities and state attributes."""
    with patch("homeassistant.components.scorpiontrack.PLATFORMS", (Platform.SENSOR,)):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    mock_scorpiontrack_client.async_get_share.assert_awaited_once_with()


async def test_heading_sensor_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test heading is registered without creating a state until enabled."""
    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get(HEADING_ENTITY_ID)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(HEADING_ENTITY_ID) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("bearing", "expected_state"),
    [
        pytest.param(0.0, "0.0", id="north"),
        pytest.param(None, STATE_UNKNOWN, id="missing"),
    ],
)
async def test_heading_sensor_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    bearing: float | None,
    expected_state: str,
) -> None:
    """Test north is valid and a missing bearing is unknown."""
    vehicle = mock_share.vehicles[0]
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share,
        vehicles=(
            replace(vehicle, position=replace(vehicle.position, bearing=bearing)),
        ),
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(HEADING_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_heading_sensor_update_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test a failed share update makes heading unavailable."""
    await setup_integration(hass, mock_config_entry)
    mock_scorpiontrack_client.async_get_share.side_effect = (
        ScorpionTrackConnectionError("Connection failed")
    )

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(HEADING_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param(ENTITY_ID, id="speed"),
        pytest.param(LAST_REPORTED_ENTITY_ID, id="last-reported"),
        pytest.param(HEADING_ENTITY_ID, id="heading"),
    ],
)
async def test_removed_vehicle_makes_sensor_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    entity_id: str,
) -> None:
    """Test a sensor becomes unavailable if its vehicle leaves the share."""
    await setup_integration(hass, mock_config_entry)

    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=()
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param(ENTITY_ID, id="speed"),
        pytest.param(HEADING_ENTITY_ID, id="heading"),
    ],
)
async def test_sensor_uses_existing_vehicle_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entity_id: str,
) -> None:
    """Test the sensor shares the vehicle device with the tracker."""
    await setup_integration(hass, mock_config_entry)

    sensor_entry = entity_registry.async_get(entity_id)
    tracker_entry = entity_registry.async_get("device_tracker.ab12_cde")
    assert sensor_entry is not None
    assert tracker_entry is not None
    assert sensor_entry.device_id == tracker_entry.device_id
    assert sensor_entry.device_id is not None

    device = device_registry.async_get(sensor_entry.device_id)
    assert device is not None
    assert device.identifiers == {("scorpiontrack", "101_1")}


async def test_last_reported_sensor_without_timestamp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test a missing timestamp is unknown without affecting the tracker."""
    vehicle = mock_share.vehicles[0]
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share,
        vehicles=(
            replace(
                vehicle,
                position=replace(vehicle.position, timestamp=None),
            ),
        ),
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(LAST_REPORTED_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    tracker_state = hass.states.get("device_tracker.ab12_cde")
    assert tracker_state is not None
    assert tracker_state.state != STATE_UNAVAILABLE
    assert tracker_state.attributes[ATTR_LATITUDE] == vehicle.position.latitude
    assert tracker_state.attributes[ATTR_LONGITUDE] == vehicle.position.longitude
