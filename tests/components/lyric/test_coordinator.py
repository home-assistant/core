"""Tests for the Honeywell Lyric coordinator."""

from unittest.mock import AsyncMock, MagicMock

from aiolyric.exceptions import LyricAuthenticationException, LyricException
import pytest

from homeassistant.components.lyric.coordinator import LyricDataUpdateCoordinator
from homeassistant.core import HomeAssistant


def _lyric_exception(
    status: int, code: str | None = "GetPriorityFailed"
) -> LyricException:
    """Build a LyricException matching aiolyric's actual payload shape."""
    return LyricException(
        {
            "request": {"method": "GET", "url": "https://example.com"},
            "response": {"code": code} if code else {},
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
    """A GetPriorityFailed 400 for one device shouldn't fail the update."""
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


async def test_get_thermostat_rooms_reraises_different_400_reason(
    coordinator: LyricDataUpdateCoordinator,
) -> None:
    """A 400 for a reason other than GetPriorityFailed should propagate.

    Guards against broadly suppressing every 400 as "unsupported device",
    which would also hide unrelated bad-request errors (e.g. a bug in our
    own request, or a new/different failure from Honeywell).
    """
    coordinator.lyric.get_thermostat_rooms.side_effect = _lyric_exception(
        400, code="SomeOtherError"
    )

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
    """One unsupported thermostat shouldn't fail the whole coordinator update."""
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
