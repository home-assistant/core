"""Tests for ZoneMinder camera entities."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import CameraState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import create_mock_monitor


@pytest.fixture(autouse=True)
def mock_getrandbits() -> Generator[None]:
    """Mock camera access token which normally is randomized."""
    with patch(
        "homeassistant.components.camera.entity.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Trigger an entity update poll."""
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("mock_zoneminder_client")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test one camera entity is created per monitor."""
    await setup_integration(hass, mock_config_entry, [Platform.CAMERA])
    await _poll(hass, freezer)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("is_recording", "is_available", "expected"),
    [
        pytest.param(True, True, CameraState.RECORDING, id="recording"),
        pytest.param(False, True, CameraState.IDLE, id="idle"),
        pytest.param(False, False, STATE_UNAVAILABLE, id="unavailable"),
    ],
)
async def test_camera_state(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    is_recording: bool,
    is_available: bool,
    expected: str,
) -> None:
    """Test the camera state follows the monitor."""
    mock_zoneminder_client.get_monitors.return_value = [
        create_mock_monitor(is_recording=is_recording, is_available=is_available)
    ]
    await setup_integration(hass, mock_config_entry, [Platform.CAMERA])
    await _poll(hass, freezer)

    assert (state := hass.states.get("camera.front_door"))
    assert state.state == expected
