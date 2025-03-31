"""Tests for the Gaposa cover component."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.gaposa.const import MOTION_DELAY
from homeassistant.components.gaposa.cover import GaposaCover
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.util.dt import utcnow

# Constants used in the tests
COVER_ID = "12345"
MOTOR_NAME = "Test Motor"


@pytest.fixture
def mock_motor():
    """Return a mock motor object."""
    motor = AsyncMock()
    motor.name = MOTOR_NAME
    motor.state = "UP"
    return motor


@pytest.fixture
def mock_coordinator(mock_motor):
    """Return a mock coordinator object."""
    coordinator = AsyncMock()
    coordinator.data = {COVER_ID: mock_motor}
    return coordinator


@pytest.fixture
def mock_platform():
    """Return a mock platform object."""
    mock_platform = AsyncMock(spec=EntityPlatform)
    mock_platform.platform_name = "test_platform"
    return mock_platform


@pytest.fixture
def cover(hass: HomeAssistant, mock_platform, mock_coordinator, mock_motor):
    """Return a GaposaCover instance."""
    cover = GaposaCover(mock_coordinator, COVER_ID, mock_motor)
    cover.add_to_platform_start(hass, mock_platform, None)
    return cover


async def test_init(hass: HomeAssistant, cover, mock_motor) -> None:
    """Test the initialization of the cover."""
    assert cover.id == COVER_ID
    assert cover.motor == mock_motor
    assert cover._attr_name == MOTOR_NAME
    assert cover.supported_features == (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )


async def test_is_closed(hass: HomeAssistant, cover) -> None:
    """Test the is_closed property."""
    cover.motor.state = "DOWN"
    assert cover.is_closed is True
    cover.motor.state = "UP"
    assert cover.is_closed is False


async def test_is_moving(hass: HomeAssistant, cover) -> None:
    """Test the is_moving property."""
    now = utcnow()
    with freeze_time(now):
        cover.lastCommand = "UP"
        cover.lastCommandTime = now
        assert cover.is_moving is True

    with freeze_time(now + timedelta(seconds=MOTION_DELAY - 1)):
        assert cover.is_moving is True

    with freeze_time(now + timedelta(seconds=MOTION_DELAY + 1)):
        assert cover.is_moving is False


async def test_open_cover(hass: HomeAssistant, cover, mock_motor) -> None:
    """Test opening the cover."""
    with (
        patch("homeassistant.components.gaposa.cover.dt_util") as mock_dt,
        patch.object(cover, "schedule_refresh_ha_after_motion") as mock_schedule,
    ):
        mock_dt.utcnow.return_value = datetime(2021, 1, 1, 12, 0, 0)
        await cover.async_open_cover()
        mock_motor.up.assert_called_once_with(False)
        assert cover.lastCommand == "UP"
        assert cover.lastCommandTime == mock_dt.utcnow()
        # Verify that refresh is scheduled
        mock_schedule.assert_called_once()


async def test_close_cover(hass: HomeAssistant, cover, mock_motor) -> None:
    """Test closing the cover."""
    with (
        patch("homeassistant.components.gaposa.cover.dt_util") as mock_dt,
        patch.object(cover, "schedule_refresh_ha_after_motion") as mock_schedule,
    ):
        mock_dt.utcnow.return_value = datetime(2021, 1, 1, 12, 0, 0)
        await cover.async_close_cover()
        mock_motor.down.assert_called_once_with(False)
        assert cover.lastCommand == "DOWN"
        assert cover.lastCommandTime == mock_dt.utcnow()
        # Verify that refresh is scheduled
        mock_schedule.assert_called_once()


async def test_stop_cover(hass: HomeAssistant, cover, mock_motor) -> None:
    """Test stopping the cover."""
    with (
        patch("homeassistant.components.gaposa.cover.dt_util") as mock_dt,
        patch.object(cover.coordinator, "async_request_refresh") as mock_refresh,
        patch.object(cover, "async_write_ha_state") as mock_write_state,
    ):
        mock_dt.utcnow.return_value = datetime(2021, 1, 1, 12, 0, 0)
        await cover.async_stop_cover()
        mock_motor.stop.assert_called_once_with(False)
        assert cover.lastCommand == "STOP"
        assert cover.lastCommandTime == mock_dt.utcnow()

        # Verify that coordinator refresh is called and state is updated immediately
        mock_refresh.assert_called_once()
        mock_write_state.assert_called_once()


# Add these new test functions


async def test_refresh_ha_after_motion(hass: HomeAssistant, cover) -> None:
    """Test that refresh_ha_after_motion updates the state correctly."""
    with (
        patch("asyncio.sleep") as mock_sleep,
        patch.object(cover.coordinator, "async_request_refresh") as mock_refresh,
        patch.object(cover, "async_write_ha_state") as mock_write_state,
    ):
        await cover.refresh_ha_after_motion()
        # Verify sleep was called with the expected delay
        mock_sleep.assert_called_once_with(MOTION_DELAY)
        # Verify coordinator refresh is called
        mock_refresh.assert_called_once()
        # Verify state is written
        mock_write_state.assert_called_once()


async def test_schedule_refresh_ha_after_motion(hass: HomeAssistant, cover) -> None:
    """Test that schedule_refresh_ha_after_motion creates a task."""

    # Mock the refresh_ha_after_motion method to avoid actual delays
    with (
        patch.object(cover, "refresh_ha_after_motion", AsyncMock()) as mock_refresh,
        patch.object(hass, "async_create_task") as mock_create_task,
    ):
        # Make async_create_task actually run the coroutine to avoid warnings
        mock_create_task.side_effect = hass.loop.create_task

        # Call the method
        cover.schedule_refresh_ha_after_motion()

        # Verify the refresh method was called
        await hass.async_block_till_done()
        mock_refresh.assert_called_once()


def test_cover_unique_id(hass: HomeAssistant, cover) -> None:
    """Test cover unique ID generation."""
    assert cover.unique_id == COVER_ID


async def test_cover_device_info(hass: HomeAssistant, cover, mock_motor) -> None:
    """Test cover device info."""
    device_info = cover.device_info
    assert device_info is not None
    assert device_info["identifiers"] == {("gaposa", COVER_ID)}
    assert device_info["name"] == MOTOR_NAME
    assert device_info["manufacturer"] == "Gaposa"


@pytest.mark.parametrize(
    ("motor_state", "expected_state"),
    [
        ("UP", False),
        ("DOWN", True),
        ("STOP", None),
        ("UNKNOWN", None),
    ],
)
async def test_cover_states(
    hass: HomeAssistant, cover, motor_state, expected_state
) -> None:
    """Test different cover states."""
    cover.motor.state = motor_state
    assert cover.is_closed is expected_state
