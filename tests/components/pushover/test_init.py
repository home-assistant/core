"""Test pushbullet integration."""
from collections.abc import Awaitable
from typing import Callable
from unittest.mock import MagicMock, patch

import aiohttp
import pushover_complete
import pytest

from homeassistant.components.notify.const import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.pushover.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MOCK_CONFIG

from tests.common import MockConfigEntry
from tests.components.repairs import get_repairs


@pytest.fixture(autouse=True)
def mock_pushover():
    """Mock pushbullet."""
    with patch("homeassistant.components.pushover.PushoverAPI") as mock_client, patch(
        "homeassistant.components.pushover.config_flow.PushoverAPI"
    ):
        mock_client.return_value._generic_post.return_value = True
        yield mock_client


async def test_setup(
    hass: HomeAssistant,
    hass_ws_client: Callable[
        [HomeAssistant], Awaitable[aiohttp.ClientWebSocketResponse]
    ],
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
    assert hass.config_entries.async_entries(DOMAIN)
    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 1
    assert issues[0]["issue_id"] == "deprecated_yaml"


async def test_async_setup_entry_success(hass: HomeAssistant) -> None:
    """Test pushover successful setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED


async def test_async_setup_entry_failed_invalid_api_key(
    hass: HomeAssistant, mock_pushover: MagicMock
) -> None:
    """Test pushover failed setup due to invalid api key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    mock_pushover.side_effect = pushover_complete.BadAPIRequestError(
        "400: application token is invalid"
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_async_setup_entry_failed_invalid_user_key(
    hass: HomeAssistant, mock_pushover: MagicMock
) -> None:
    """Test pushover failed setup due to invalid user key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    mock_pushover.side_effect = pushover_complete.BadAPIRequestError(
        "400: user key is invalid"
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_ERROR
