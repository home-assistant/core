"""Tests for the Gaposa cover component."""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.gaposa.const import MOTION_DELAY
from homeassistant.components.gaposa.cover import GaposaCover
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.util.dt import utcnow

from tests.common import async_test_home_assistant

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
async def hass():
    """Return a HomeAssistant instance."""
    hass = await async_test_home_assistant(asyncio.get_running_loop())
    yield hass
    await hass.async_stop()


@pytest.fixture
def mock_platform():
    """Return a mock platform object."""
    mock_platform = AsyncMock(spec=EntityPlatform)
    mock_platform.platform_name = "test_platform"
    return mock_platform


@pytest.fixture
def cover(hass, mock_platform, mock_coordinator, mock_motor):
    """Return a GaposaCover instance."""
    cover = GaposaCover(mock_coordinator, COVER_ID, mock_motor)
    cover.add_to_platform_start(hass, mock_platform, None)
    return cover


async def test_init(hass, cover, mock_motor) -> None:
    """Test the initialization of the cover."""
    assert cover.id == COVER_ID
    assert cover.motor == mock_motor
    assert cover._attr_name == MOTOR_NAME
    assert cover.supported_features == (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )


async def test_is_closed(hass, cover) -> None:
    """Test the is_closed property."""
    cover.motor.state = "DOWN"
    assert cover.is_closed is True
    cover.motor.state = "UP"
    assert cover.is_closed is False


async def test_is_moving(hass, cover) -> None:
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


async def test_open_cover(hass, cover, mock_motor) -> None:
    """Test opening the cover."""
    with patch("homeassistant.components.gaposa.cover.dt_util") as mock_dt:
        mock_dt.utcnow.return_value = datetime(2021, 1, 1, 12, 0, 0)
        await cover.async_open_cover()
        mock_motor.up.assert_called_once_with(False)
        assert cover.lastCommand == "UP"
        assert cover.lastCommandTime == mock_dt.utcnow()


async def test_close_cover(hass, cover, mock_motor) -> None:
    """Test closing the cover."""
    with patch("homeassistant.components.gaposa.cover.dt_util") as mock_dt:
        mock_dt.utcnow.return_value = datetime(2021, 1, 1, 12, 0, 0)
        await cover.async_close_cover()
        mock_motor.down.assert_called_once_with(False)
        assert cover.lastCommand == "DOWN"
        assert cover.lastCommandTime == mock_dt.utcnow()


async def test_stop_cover(hass, cover, mock_motor) -> None:
    """Test stopping the cover."""
    with patch("homeassistant.components.gaposa.cover.dt_util") as mock_dt:
        mock_dt.utcnow.return_value = datetime(2021, 1, 1, 12, 0, 0)
        await cover.async_stop_cover()
        mock_motor.stop.assert_called_once_with(False)
        assert cover.lastCommand == "STOP"
        assert cover.lastCommandTime == mock_dt.utcnow()


# Additional tests can be added for other methods and properties as needed.
