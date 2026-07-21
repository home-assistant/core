"""Tests for the Honeywell Lyric coordinator."""

from unittest.mock import AsyncMock, MagicMock

from aiolyric.exceptions import LyricAuthenticationException, LyricException
import pytest

from homeassistant.components.lyric.coordinator import LyricDataUpdateCoordinator
from homeassistant.core import HomeAssistant


def _lyric_exception(status: int) -> LyricException:
    """Build a LyricException matching aiolyric's actual payload shape."""
    return LyricException(
        {
            "request": {"method": "GET", "url": "https://example.com"},
            "response": {"message": "GetPriorityFailed"},
            "status": status,
        }
    )


@pytest.fixture
def coordinator(hass: HomeAssistant) -> LyricDataUpdateCoordinator:
    """Return a coordinator with a mocked Lyric client."""
    return LyricDataUpdateCoordinator(
        hass,
        config_entry=MagicMock(),
        oauth_session=AsyncMock(),
        lyric=AsyncMock(),
    )


async def test_get_thermostat_rooms_ignores_unsupported_device(
    coordinator: LyricDataUpdateCoordinator,
) -> None:
    """A 400 GetPriorityFailed for one device shouldn't fail the update.

    Devices that don't support the room priority endpoint (e.g. older
    thermostats) return a 400 here; that's expected and must not be
    conflated with devices that do support it but got skipped by a
    device ID heuristic. aiolyric raises this as a plain LyricException,
    not ClientResponseError, with the HTTP status embedded in the
    exception's payload rather than a status attribute.
    """
    coordinator.lyric.get_thermostat_rooms.side_effect = _lyric_exception(400)

    await coordinator._get_thermostat_rooms("location1", "device1")

    coordinator.lyric.get_thermostat_rooms.assert_called_once_with(
        "location1", "device1"
    )


async def test_get_thermostat_rooms_reraises_other_errors(
    coordinator: LyricDataUpdateCoordinator,
) -> None:
    """Non-400 errors should still propagate to fail the update."""
    coordinator.lyric.get_thermostat_rooms.side_effect = _lyric_exception(500)

    with pytest.raises(LyricException):
        await coordinator._get_thermostat_rooms("location1", "device1")


async def test_get_thermostat_rooms_reraises_authentication_errors(
    coordinator: LyricDataUpdateCoordinator,
) -> None:
    """Authentication errors must propagate for the caller's retry logic.

    LyricAuthenticationException is a LyricException subclass, so it must
    not be caught by the same handler that swallows the 400 case.
    """
    coordinator.lyric.get_thermostat_rooms.side_effect = LyricAuthenticationException(
        {"request": {}, "response": {}, "status": 401}
    )

    with pytest.raises(LyricAuthenticationException):
        await coordinator._get_thermostat_rooms("location1", "device1")


async def test_get_thermostat_rooms_success(
    coordinator: LyricDataUpdateCoordinator,
) -> None:
    """A supported device should have its room data fetched normally."""
    await coordinator._get_thermostat_rooms("location1", "device1")

    coordinator.lyric.get_thermostat_rooms.assert_called_once_with(
        "location1", "device1"
    )


async def test_run_update_skips_unsupported_device(
    coordinator: LyricDataUpdateCoordinator,
) -> None:
    """One unsupported thermostat shouldn't fail the whole coordinator update.

    Regression test for the original bug: previously, any thermostat
    that didn't support the priority endpoint made the entire refresh
    fail with UpdateFailed, since aiolyric's LyricException (not
    ClientResponseError) went uncaught by _get_thermostat_rooms and
    propagated to the outer handler.
    """
    supported = MagicMock(device_class="Thermostat", device_id="device-ok")
    unsupported = MagicMock(device_class="Thermostat", device_id="device-400")
    location = MagicMock(location_id="location1", devices=[supported, unsupported])
    coordinator.lyric.locations = [location]

    async def get_thermostat_rooms(location_id: str, device_id: str) -> None:
        if device_id == "device-400":
            raise _lyric_exception(400)

    coordinator.lyric.get_thermostat_rooms.side_effect = get_thermostat_rooms

    result = await coordinator._run_update(False)

    assert result is coordinator.lyric
    assert coordinator.lyric.get_thermostat_rooms.call_count == 2
