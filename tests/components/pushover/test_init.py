"""Test pushbullet integration."""
from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, patch

import aiohttp
from pushover_complete import BadAPIRequestError
import pytest
import requests_mock

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.pushover.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MOCK_CONFIG

from tests.common import MockConfigEntry
from tests.components.repairs import get_repairs


@pytest.fixture(autouse=False)
def mock_pushover():
    """Mock pushover."""
    with patch(
        "pushover_complete.PushoverAPI._generic_post", return_value={}
    ) as mock_generic_post:
        yield mock_generic_post


async def test_setup(
    hass: HomeAssistant,
    hass_ws_client: Callable[
        [HomeAssistant], Awaitable[aiohttp.ClientWebSocketResponse]
    ],
    mock_pushover: MagicMock,
) -> None:
    """Test integration failed due to an error."""
    assert await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {
                    "name": "Pushover",
                    "platform": "pushover",
                    "api_key": "MYAPIKEY",
                    "user_key": "MYUSERKEY",
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(DOMAIN)
    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 1
    assert issues[0]["issue_id"] == "removed_yaml"


async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_pushover: MagicMock
) -> None:
    """Test pushover successful setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED


async def test_unique_id_updated(hass: HomeAssistant, mock_pushover: MagicMock) -> None:
    """Test updating unique_id to new format."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id="MYUSERKEY")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    assert entry.unique_id is None


async def test_async_setup_entry_failed_invalid_api_key(
    hass: HomeAssistant, mock_pushover: MagicMock
) -> None:
    """Test pushover failed setup due to invalid api key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    mock_pushover.side_effect = BadAPIRequestError("400: application token is invalid")
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_async_setup_entry_failed_conn_error(
    hass: HomeAssistant, mock_pushover: MagicMock
) -> None:
    """Test pushover failed setup due to conn error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    mock_pushover.side_effect = BadAPIRequestError
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_failed_json_error(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test pushover failed setup due to bad json response from library."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    requests_mock.post(
        "https://api.pushover.net/1/users/validate.json", status_code=204
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY
