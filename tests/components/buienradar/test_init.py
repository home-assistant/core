"""Tests for the buienradar component."""

from http import HTTPStatus

from buienradar.urls import JSON_FEED_URL
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.usefixtures("mock_buienradar_feeds")
async def test_load_unload(hass: HomeAssistant) -> None:
    """Test loading and unloading a config entry."""
    entry = await setup_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_when_fetch_fails(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup is retried when the first update fails."""
    aioclient_mock.get(JSON_FEED_URL, status=HTTPStatus.NOT_FOUND)

    entry = await setup_integration(hass)

    assert entry.state is ConfigEntryState.SETUP_RETRY
