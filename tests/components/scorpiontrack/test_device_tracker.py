"""Test the ScorpionTrack device tracker platform."""

from dataclasses import replace
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyscorpiontrack import ScorpionTrackConnectionError, ScorpionTrackShare
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.scorpiontrack.const import DEFAULT_SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_device_tracker_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the ScorpionTrack device tracker state and attributes."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_removed_vehicle_becomes_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test a tracker becomes unavailable if its vehicle leaves the share."""
    await setup_integration(hass, mock_config_entry)

    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=()
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.ab12_cde")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_connection_error_makes_tracker_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test a tracker becomes unavailable after a refresh connection error."""
    await setup_integration(hass, mock_config_entry)

    mock_scorpiontrack_client.async_get_share.side_effect = (
        ScorpionTrackConnectionError("Connection failed")
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.ab12_cde")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_new_vehicles_after_setup_do_not_add_tracker_entities(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Vehicles that appear later should wait for a future dynamic-device PR."""
    await setup_integration(hass, mock_config_entry)

    new_vehicle = replace(
        mock_share.vehicles[0],
        id=2,
        name="Tiguan",
        registration="EF34 ABC",
        model="Tiguan",
    )
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=(*mock_share.vehicles, new_vehicle)
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.ef34_abc") is None
