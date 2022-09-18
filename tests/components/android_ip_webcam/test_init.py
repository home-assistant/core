"""Tests for the Android IP Webcam integration."""


from collections.abc import Awaitable
from typing import Callable
from unittest.mock import Mock

import aiohttp

from homeassistant.components.android_ip_webcam.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.repairs import get_repairs
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_CONFIG_DATA = {
    "name": "IP Webcam",
    "host": "1.1.1.1",
    "port": 8080,
    "username": "user",
    "password": "pass",
}


async def test_setup(
    hass: HomeAssistant,
    aioclient_mock_fixture,
    hass_ws_client: Callable[
        [HomeAssistant], Awaitable[aiohttp.ClientWebSocketResponse]
    ],
) -> None:
    """Test integration failed due to an error."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: [MOCK_CONFIG_DATA]})
    assert hass.config_entries.async_entries(DOMAIN)
    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 1
    assert issues[0]["issue_id"] == "deprecated_yaml"


async def test_successful_config_entry(
    hass: HomeAssistant, aioclient_mock_fixture
) -> None:
    """Test settings up integration from config entry."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ConfigEntryState.LOADED


async def test_setup_failed_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test integration failed due to connection error."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)
    aioclient_mock.get(
        "http://1.1.1.1:8080/status.json?show_avail=1",
        exc=aiohttp.ClientError,
    )

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_failed_invalid_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test integration failed due to invalid auth."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)
    aioclient_mock.get(
        "http://1.1.1.1:8080/status.json?show_avail=1",
        exc=aiohttp.ClientResponseError(Mock(), (), status=401),
    )

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant, aioclient_mock_fixture) -> None:
    """Test removing integration."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data[DOMAIN]
