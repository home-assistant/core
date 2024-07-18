"""Tests for the DoorBird integration."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import aiohttp
from doorbirdpy import DoorBirdScheduleEntry

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME

VALID_CONFIG = {
    CONF_HOST: "1.2.3.4",
    CONF_USERNAME: "friend",
    CONF_PASSWORD: "password",
    CONF_NAME: "mydoorbird",
}


def get_mock_doorbirdapi_return_values(
    info: dict[str, Any] | None = None,
    schedule: list[DoorBirdScheduleEntry] | None = None,
) -> MagicMock:
    """Return a mock DoorBirdAPI object with return values."""
    doorbirdapi_mock = MagicMock()
    type(doorbirdapi_mock).info = AsyncMock(return_value=info)
    type(doorbirdapi_mock).favorites = AsyncMock(return_value={})
    type(doorbirdapi_mock).change_favorite = AsyncMock(return_value=True)
    type(doorbirdapi_mock).schedule = AsyncMock(return_value=schedule)
    type(doorbirdapi_mock).doorbell_state = AsyncMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=Mock(), history=Mock(), status=401
        )
    )
    return doorbirdapi_mock


def get_mock_doorbirdapi_side_effects(info: dict[str, Any] | None = None) -> MagicMock:
    """Return a mock DoorBirdAPI object with side effects."""
    doorbirdapi_mock = MagicMock()
    type(doorbirdapi_mock).info = AsyncMock(side_effect=info)
    return doorbirdapi_mock
