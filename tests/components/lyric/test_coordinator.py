"""Tests for the Honeywell Lyric coordinator."""

from unittest.mock import AsyncMock, MagicMock

from aiohttp.client_exceptions import ClientResponseError
import pytest

from homeassistant.components.lyric.coordinator import LyricDataUpdateCoordinator
from homeassistant.core import HomeAssistant


@pytest.fixture
def coordinator(hass: HomeAssistant) -> LyricDataUpdateCoordinator:
    """Return a coordinator with a mocked Lyric client."""
    return LyricDataUpdateCoordinator(
        hass,
        config_entry=MagicMock(),
        oauth_session=MagicMock(),
        lyric=AsyncMock(),
    )


async def test_get_thermostat_rooms_ignores_unsupported_device(
    coordinator: LyricDataUpdateCoordinator,
) -> None:
    """A 400 GetPriorityFailed for one device shouldn't fail the update.

    Devices that don't support the room priority endpoint (e.g. older
    thermostats) return a 400 here; that's expected and must not be
    conflated with devices that do support it but got skipped by a
    device ID heuristic.
    """
    coordinator.lyric.get_thermostat_rooms.side_effect = ClientResponseError(
        request_info=MagicMock(), history=(), status=400
    )

    await coordinator._get_thermostat_rooms("location1", "device1")

    coordinator.lyric.get_thermostat_rooms.assert_called_once_with(
        "location1", "device1"
    )


async def test_get_thermostat_rooms_reraises_other_errors(
    coordinator: LyricDataUpdateCoordinator,
) -> None:
    """Non-400 errors should still propagate to fail the update."""
    coordinator.lyric.get_thermostat_rooms.side_effect = ClientResponseError(
        request_info=MagicMock(), history=(), status=500
    )

    with pytest.raises(ClientResponseError):
        await coordinator._get_thermostat_rooms("location1", "device1")


async def test_get_thermostat_rooms_success(
    coordinator: LyricDataUpdateCoordinator,
) -> None:
    """A supported device should have its room data fetched normally."""
    await coordinator._get_thermostat_rooms("location1", "device1")

    coordinator.lyric.get_thermostat_rooms.assert_called_once_with(
        "location1", "device1"
    )
