"""Tests for the DoorBird integration."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import aiohttp
from doorbirdpy import DoorBird, DoorBirdScheduleEntry

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME

VALID_CONFIG = {
    CONF_HOST: "1.2.3.4",
    CONF_USERNAME: "friend",
    CONF_PASSWORD: "password",
    CONF_NAME: "mydoorbird",
}


def mock_unauthorized_exception() -> aiohttp.ClientResponseError:
    """Return a mock unauthorized exception."""
    return aiohttp.ClientResponseError(request_info=Mock(), history=Mock(), status=401)


def get_mock_doorbird_api(
    info: dict[str, Any] | None = None,
    info_side_effect: Exception | None = None,
    schedule: list[DoorBirdScheduleEntry] | None = None,
) -> DoorBird:
    """Return a mock DoorBirdAPI object with return values."""
    doorbirdapi_mock = MagicMock(spec_set=DoorBird)
    type(doorbirdapi_mock).info = AsyncMock(
        side_effect=info_side_effect, return_value=info
    )
    type(doorbirdapi_mock).favorites = AsyncMock(return_value={})
    type(doorbirdapi_mock).change_favorite = AsyncMock(return_value=True)
    type(doorbirdapi_mock).schedule = AsyncMock(return_value=schedule)
    type(doorbirdapi_mock).doorbell_state = AsyncMock(
        side_effect=mock_unauthorized_exception()
    )
    return doorbirdapi_mock
