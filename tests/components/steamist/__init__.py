"""Tests for the Steamist integration."""
from contextlib import contextmanager
from unittest.mock import patch

from aiosteamist import SteamistStatus

MOCK_ASYNC_GET_STATUS_INACTIVE = SteamistStatus(
    temp=70, temp_units="F", minutes_remain=0, active=False
)
MOCK_ASYNC_GET_STATUS_ACTIVE = SteamistStatus(
    temp=102, temp_units="F", minutes_remain=14, active=True
)


def _patch_status_inactive():
    @contextmanager
    def _patcher():
        with patch(
            "homeassistant.components.steamist.Steamist.async_get_status",
            return_value=MOCK_ASYNC_GET_STATUS_INACTIVE,
        ):
            yield

    return _patcher()


def _patch_status_active():
    @contextmanager
    def _patcher():
        with patch(
            "homeassistant.components.steamist.Steamist.async_get_status",
            return_value=MOCK_ASYNC_GET_STATUS_ACTIVE,
        ):
            yield

    return _patcher()
