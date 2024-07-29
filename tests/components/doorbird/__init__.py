"""Tests for the DoorBird integration."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import aiohttp
from doorbirdpy import DoorBird, DoorBirdScheduleEntry

from homeassistant import config_entries
from homeassistant.components.doorbird.const import API_URL
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)

VALID_CONFIG = {
    CONF_HOST: "1.2.3.4",
    CONF_USERNAME: "friend",
    CONF_PASSWORD: "password",
    CONF_NAME: "mydoorbird",
}


def _get_aiohttp_client_error(status: int) -> aiohttp.ClientResponseError:
    """Return a mock aiohttp client response error."""
    return aiohttp.ClientResponseError(
        request_info=Mock(),
        history=Mock(),
        status=status,
    )


def mock_unauthorized_exception() -> aiohttp.ClientResponseError:
    """Return a mock unauthorized exception."""
    return _get_aiohttp_client_error(401)


def mock_not_found_exception() -> aiohttp.ClientResponseError:
    """Return a mock not found exception."""
    return _get_aiohttp_client_error(404)


def get_mock_doorbird_api(
    info: dict[str, Any] | None = None,
    info_side_effect: Exception | None = None,
    schedule: list[DoorBirdScheduleEntry] | None = None,
    favorites: dict[str, dict[str, Any]] | None = None,
    favorites_side_effect: Exception | None = None,
    change_schedule: tuple[bool, int] | None = None,
) -> DoorBird:
    """Return a mock DoorBirdAPI object with return values."""
    doorbirdapi_mock = MagicMock(spec_set=DoorBird)
    type(doorbirdapi_mock).info = AsyncMock(
        side_effect=info_side_effect, return_value=info
    )
    type(doorbirdapi_mock).favorites = AsyncMock(
        side_effect=favorites_side_effect,
        return_value=favorites,
    )
    type(doorbirdapi_mock).change_favorite = AsyncMock(return_value=True)
    type(doorbirdapi_mock).change_schedule = AsyncMock(
        return_value=change_schedule or (True, 200)
    )
    type(doorbirdapi_mock).schedule = AsyncMock(return_value=schedule)
    type(doorbirdapi_mock).energize_relay = AsyncMock(return_value=True)
    type(doorbirdapi_mock).turn_light_on = AsyncMock(return_value=True)
    type(doorbirdapi_mock).delete_favorite = AsyncMock(return_value=True)
    type(doorbirdapi_mock).get_image = AsyncMock(return_value=b"image")
    type(doorbirdapi_mock).doorbell_state = AsyncMock(
        side_effect=mock_unauthorized_exception()
    )
    return doorbirdapi_mock


async def mock_webhook_call(
    config_entry: config_entries.ConfigEntry,
    aiohttp_client: aiohttp.ClientSession,
    event: str,
) -> None:
    """Mock the webhook call."""
    token = config_entry.data.get(CONF_TOKEN, config_entry.entry_id)
    response = await aiohttp_client.get(f"{API_URL}/{event}?token={token}")
    response.raise_for_status()
