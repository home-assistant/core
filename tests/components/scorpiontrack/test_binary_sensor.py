"""Test the ScorpionTrack binary sensor platform."""

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
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "binary_sensor.ab12_cde_ignition"


async def test_ignition_binary_sensor_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test the ignition binary sensor uses the coordinator snapshot."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert ATTR_LATITUDE not in state.attributes
    assert ATTR_LONGITUDE not in state.attributes
    mock_scorpiontrack_client.async_get_share.assert_awaited_once_with()


async def test_ignition_binary_sensor_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the ignition binary sensor entity and state attributes."""
    with patch(
        "homeassistant.components.scorpiontrack.PLATFORMS", (Platform.BINARY_SENSOR,)
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("ignition", "expected_state"),
    [
        pytest.param(True, STATE_ON, id="on"),
        pytest.param(False, STATE_OFF, id="off"),
        pytest.param(None, STATE_UNAVAILABLE, id="missing"),
    ],
)
async def test_ignition_binary_sensor_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    ignition: bool | None,
    expected_state: str,
) -> None:
    """Test on, off, and missing ignition values."""
    vehicle = mock_share.vehicles[0]
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share,
        vehicles=(
            replace(
                vehicle,
                position=replace(vehicle.position, ignition=ignition),
            ),
        ),
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


async def test_removed_vehicle_makes_ignition_binary_sensor_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test ignition becomes unavailable if its vehicle leaves the share."""
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


async def test_ignition_binary_sensor_uses_existing_vehicle_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test ignition shares the vehicle device with the tracker."""
    await setup_integration(hass, mock_config_entry)

    ignition_entry = entity_registry.async_get(ENTITY_ID)
    tracker_entry = entity_registry.async_get("device_tracker.ab12_cde")
    assert ignition_entry is not None
    assert tracker_entry is not None
    assert ignition_entry.unique_id == "101_1_ignition"
    assert ignition_entry.original_device_class is None
    assert ignition_entry.device_id == tracker_entry.device_id
    assert ignition_entry.device_id is not None
