"""Tests for PAJ GPS sensor platform."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pajgps_api.models.trackpoint import TrackPoint
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.paj_gps.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


async def test_all_entities(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensor entities against snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_speed_none_when_missing(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that speed state is unknown when the trackpoint has no speed value."""
    mock_paj_gps_api.get_all_last_positions.return_value = [
        TrackPoint(iddevice=1, speed=None)
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.device_1_speed")
    assert state is not None
    assert state.state == STATE_UNKNOWN
