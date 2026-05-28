"""Tests for PAJ GPS device tracker."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pajgps_api.models.device import Device
from pajgps_api.models.trackpoint import TrackPoint
from pajgps_api.pajgps_api_error import PajGpsApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.paj_gps.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def device_tracker_only() -> Generator[None]:
    """Enable only the device tracker platform."""
    with patch(
        "homeassistant.components.paj_gps.PLATFORMS",
        [Platform.DEVICE_TRACKER],
    ):
        yield


async def test_all_entities(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all device tracker entities against snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_entity_unavailable_on_coordinator_error(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that entity becomes unavailable when the coordinator update fails."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("device_tracker.device_1")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_paj_gps_api.get_devices.side_effect = PajGpsApiError("API error")

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.device_1").state == STATE_UNAVAILABLE


async def test_entity_recovers_after_coordinator_error(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the entity recovers after a transient coordinator error."""
    await setup_integration(hass, mock_config_entry)

    mock_paj_gps_api.get_devices.side_effect = PajGpsApiError("API error")
    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.device_1").state == STATE_UNAVAILABLE

    mock_paj_gps_api.get_devices.side_effect = None
    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.device_1").state != STATE_UNAVAILABLE


async def test_device_removed_from_account(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entity becomes unavailable when the device disappears from the account."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("device_tracker.device_1").state != STATE_UNAVAILABLE

    mock_paj_gps_api.get_devices.return_value = []
    mock_paj_gps_api.get_all_last_positions.return_value = []

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.device_1").state == STATE_UNAVAILABLE


async def test_new_device_added_dynamically(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a new entity is added when a new device appears in coordinator data."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("device_tracker.device_1") is not None
    assert hass.states.get("device_tracker.device_2") is None

    new_device = Device(id=2, name="Device 2", device_models=[])
    new_trackpoint = TrackPoint(iddevice=2, lat=48.8566, lng=2.3522)

    mock_paj_gps_api.get_devices.return_value = [
        *mock_paj_gps_api.get_devices.return_value,
        new_device,
    ]
    mock_paj_gps_api.get_all_last_positions.return_value = [
        *mock_paj_gps_api.get_all_last_positions.return_value,
        new_trackpoint,
    ]

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.device_2") is not None


@pytest.mark.parametrize(
    ("lat", "lng", "expected_lat", "expected_lng"),
    [
        (None, 13.0, None, None),
        (52.0, None, None, None),
        (52.0, 13.0, 52.0, 13.0),
    ],
    ids=["no_latitude", "no_longitude", "valid_position"],
)
async def test_position_none_when_coordinates_missing(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    lat: float | None,
    lng: float | None,
    expected_lat: float | None,
    expected_lng: float | None,
) -> None:
    """Test that latitude/longitude are None when coordinates are missing."""
    mock_paj_gps_api.get_all_last_positions.return_value = [
        TrackPoint(iddevice=1, lat=lat, lng=lng)
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("device_tracker.device_1")
    assert state is not None
    assert state.attributes.get("latitude") == expected_lat
    assert state.attributes.get("longitude") == expected_lng
