"""Tests for the Steamist integration."""
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from aiosteamist import Steamist, SteamistStatus

MOCK_ASYNC_GET_STATUS_INACTIVE = SteamistStatus(
    temp=70, temp_units="F", minutes_remain=0, active=False
)
MOCK_ASYNC_GET_STATUS_ACTIVE = SteamistStatus(
    temp=102, temp_units="F", minutes_remain=14, active=True
)


def _mocked_steamist() -> Steamist:
    client = MagicMock(auto_spec=Steamist)
    client.async_turn_on_steam = AsyncMock()
    client.async_turn_off_steam = AsyncMock()
    client.async_get_status = AsyncMock(return_value=MOCK_ASYNC_GET_STATUS_ACTIVE)
    return client


def _patch_status_active(client=None):
    if client is None:
        client = _mocked_steamist()
        client.async_get_status = AsyncMock(return_value=MOCK_ASYNC_GET_STATUS_ACTIVE)

    @contextmanager
    def _patcher():
        with patch("homeassistant.components.steamist.Steamist", return_value=client):
            yield

    return _patcher()


def _patch_status_inactive(client=None):
    if client is None:
        client = _mocked_steamist()
        client.async_get_status = AsyncMock(return_value=MOCK_ASYNC_GET_STATUS_INACTIVE)

    @contextmanager
    def _patcher():
        with patch("homeassistant.components.steamist.Steamist", return_value=client):
            yield

    return _patcher()
