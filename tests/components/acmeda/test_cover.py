"""Tests for the Acmeda cover module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.acmeda.const import DOMAIN
from homeassistant.components.acmeda.cover import AcmedaCover
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
    )
    mock_config_entry.add_to_hass(hass)
    return mock_config_entry


@pytest.fixture
def mock_roller() -> MagicMock:
    """Return a mocked Acmeda roller."""
    roller = MagicMock()
    roller.id = 1234567890123
    roller.name = "Test Roller"
    roller.type = 1
    roller.closed_percent = 50
    return roller


@pytest.fixture
def acmeda_cover(mock_roller: MagicMock) -> AcmedaCover:
    """Return an AcmedaCover instance."""
    return AcmedaCover(mock_roller)


async def test_current_cover_position_with_value(acmeda_cover: AcmedaCover) -> None:
    """Test current_cover_position returns correct position when value is set."""
    acmeda_cover.roller.closed_percent = 50
    assert acmeda_cover.current_cover_position == 50


async def test_current_cover_position_when_closed(acmeda_cover: AcmedaCover) -> None:
    """Test current_cover_position returns 0 when cover is closed."""
    acmeda_cover.roller.closed_percent = 100
    assert acmeda_cover.current_cover_position == 0


async def test_current_cover_position_when_open(acmeda_cover: AcmedaCover) -> None:
    """Test current_cover_position returns 100 when cover is open."""
    acmeda_cover.roller.closed_percent = 0
    assert acmeda_cover.current_cover_position == 100


async def test_current_cover_position_when_none(acmeda_cover: AcmedaCover) -> None:
    """Test current_cover_position returns None when closed_percent is None."""
    acmeda_cover.roller.closed_percent = None
    assert acmeda_cover.current_cover_position is None


async def test_current_cover_tilt_position_with_value(
    acmeda_cover: AcmedaCover,
) -> None:
    """Test current_cover_tilt_position returns correct position when value is set."""
    acmeda_cover.roller.closed_percent = 50
    assert acmeda_cover.current_cover_tilt_position == 50


async def test_current_cover_tilt_position_when_closed(
    acmeda_cover: AcmedaCover,
) -> None:
    """Test current_cover_tilt_position returns 0 when cover is closed."""
    acmeda_cover.roller.closed_percent = 100
    assert acmeda_cover.current_cover_tilt_position == 0


async def test_current_cover_tilt_position_when_open(
    acmeda_cover: AcmedaCover,
) -> None:
    """Test current_cover_tilt_position returns 100 when cover is open."""
    acmeda_cover.roller.closed_percent = 0
    assert acmeda_cover.current_cover_tilt_position == 100


async def test_current_cover_tilt_position_when_none(
    acmeda_cover: AcmedaCover,
) -> None:
    """Test current_cover_tilt_position returns None when closed_percent is None."""
    acmeda_cover.roller.closed_percent = None
    assert acmeda_cover.current_cover_tilt_position is None


async def test_supported_features_type_not_7(acmeda_cover: AcmedaCover) -> None:
    """Test supported_features for roller type not 7."""
    acmeda_cover.roller.type = 1
    expected = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    assert acmeda_cover.supported_features == expected


async def test_supported_features_type_7(acmeda_cover: AcmedaCover) -> None:
    """Test supported_features for roller type 7."""
    acmeda_cover.roller.type = 7
    expected = (
        CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )
    assert acmeda_cover.supported_features == expected


async def test_supported_features_type_10(acmeda_cover: AcmedaCover) -> None:
    """Test supported_features for roller type 10."""
    acmeda_cover.roller.type = 10
    expected = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )
    assert acmeda_cover.supported_features == expected


async def test_is_closed_when_closed(acmeda_cover: AcmedaCover) -> None:
    """Test is_closed returns True when cover is closed."""
    acmeda_cover.roller.closed_percent = 100
    assert acmeda_cover.is_closed is True


async def test_is_closed_when_open(acmeda_cover: AcmedaCover) -> None:
    """Test is_closed returns False when cover is open."""
    acmeda_cover.roller.closed_percent = 0
    assert acmeda_cover.is_closed is False


async def test_is_closed_when_partially_open(acmeda_cover: AcmedaCover) -> None:
    """Test is_closed returns False when cover is partially open."""
    acmeda_cover.roller.closed_percent = 50
    assert acmeda_cover.is_closed is False


async def test_is_closed_when_none(acmeda_cover: AcmedaCover) -> None:
    """Test is_closed returns None when closed_percent is None."""
    acmeda_cover.roller.closed_percent = None
    assert acmeda_cover.is_closed is None


async def test_async_close_cover(acmeda_cover: AcmedaCover) -> None:
    """Test async_close_cover calls move_down."""
    acmeda_cover.roller.move_down = AsyncMock()
    await acmeda_cover.async_close_cover()
    acmeda_cover.roller.move_down.assert_called_once()


async def test_async_open_cover(acmeda_cover: AcmedaCover) -> None:
    """Test async_open_cover calls move_up."""
    acmeda_cover.roller.move_up = AsyncMock()
    await acmeda_cover.async_open_cover()
    acmeda_cover.roller.move_up.assert_called_once()


async def test_async_stop_cover(acmeda_cover: AcmedaCover) -> None:
    """Test async_stop_cover calls move_stop."""
    acmeda_cover.roller.move_stop = AsyncMock()
    await acmeda_cover.async_stop_cover()
    acmeda_cover.roller.move_stop.assert_called_once()


async def test_async_set_cover_position(acmeda_cover: AcmedaCover) -> None:
    """Test async_set_cover_position calls move_to with correct position."""
    acmeda_cover.roller.move_to = AsyncMock()
    await acmeda_cover.async_set_cover_position(**{"position": 75})
    acmeda_cover.roller.move_to.assert_called_once_with(25)


async def test_async_close_cover_tilt(acmeda_cover: AcmedaCover) -> None:
    """Test async_close_cover_tilt calls move_down."""
    acmeda_cover.roller.move_down = AsyncMock()
    await acmeda_cover.async_close_cover_tilt()
    acmeda_cover.roller.move_down.assert_called_once()


async def test_async_open_cover_tilt(acmeda_cover: AcmedaCover) -> None:
    """Test async_open_cover_tilt calls move_up."""
    acmeda_cover.roller.move_up = AsyncMock()
    await acmeda_cover.async_open_cover_tilt()
    acmeda_cover.roller.move_up.assert_called_once()


async def test_async_stop_cover_tilt(acmeda_cover: AcmedaCover) -> None:
    """Test async_stop_cover_tilt calls move_stop."""
    acmeda_cover.roller.move_stop = AsyncMock()
    await acmeda_cover.async_stop_cover_tilt()
    acmeda_cover.roller.move_stop.assert_called_once()


async def test_async_set_cover_tilt_position(acmeda_cover: AcmedaCover) -> None:
    """Test async_set_cover_tilt_position calls move_to with correct position."""
    acmeda_cover.roller.move_to = AsyncMock()
    await acmeda_cover.async_set_cover_tilt_position(**{"tilt_position": 75})
    acmeda_cover.roller.move_to.assert_called_once_with(25)
