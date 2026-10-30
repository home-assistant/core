"""Test ScorpionTrack measurement availability during updates."""

from dataclasses import replace
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyscorpiontrack import (
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShare,
    ScorpionTrackShareUnavailableError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.scorpiontrack.const import DEFAULT_SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import setup_integration

SPEED_ENTITY_ID = "sensor.ab12_cde_speed"
IGNITION_ENTITY_ID = "binary_sensor.ab12_cde_ignition"


@pytest.mark.parametrize(
    ("field", "entity_id", "sibling_id"),
    [
        pytest.param("speed_kmh", SPEED_ENTITY_ID, IGNITION_ENTITY_ID, id="speed"),
        pytest.param("ignition", IGNITION_ENTITY_ID, SPEED_ENTITY_ID, id="ignition"),
    ],
)
async def test_missing_measurement_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    field: str,
    entity_id: str,
    sibling_id: str,
) -> None:
    """Test a missing reading is unknown without affecting other entities."""
    await setup_integration(hass, mock_config_entry)
    original = hass.states.get(entity_id)
    sibling = hass.states.get(sibling_id)
    tracker = hass.states.get("device_tracker.ab12_cde")
    assert original is not None
    assert sibling is not None
    assert tracker is not None

    vehicle = mock_share.vehicles[0]
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share,
        vehicles=(
            replace(vehicle, position=replace(vehicle.position, **{field: None})),
        ),
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    assert hass.states.get(sibling_id).state == sibling.state
    updated_tracker = hass.states.get(tracker.entity_id)
    assert updated_tracker is not None
    assert updated_tracker.state == tracker.state
    assert updated_tracker.attributes == tracker.attributes

    mock_scorpiontrack_client.async_get_share.return_value = mock_share
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == original.state
    assert mock_scorpiontrack_client.async_get_share.await_count == 3


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ScorpionTrackConnectionError(), id="connection"),
        pytest.param(ScorpionTrackInvalidTokenError(), id="invalid_token"),
        pytest.param(ScorpionTrackShareUnavailableError(), id="unavailable_share"),
    ],
)
@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param(SPEED_ENTITY_ID, id="speed"),
        pytest.param(IGNITION_ENTITY_ID, id="ignition"),
    ],
)
async def test_failed_share_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    error: Exception,
    entity_id: str,
) -> None:
    """Test a failed share update is unavailable until a successful update."""
    await setup_integration(hass, mock_config_entry)
    original = hass.states.get(entity_id)
    assert original is not None

    mock_scorpiontrack_client.async_get_share.side_effect = error
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_scorpiontrack_client.async_get_share.side_effect = None
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == original.state
    assert mock_scorpiontrack_client.async_get_share.await_count == 3
