"""Test the Tessie init."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import (
    ERROR_AUTH,
    ERROR_CONNECTION,
    ERROR_UNKNOWN,
    TEST_VEHICLES,
    URL_VEHICLES,
    setup_platform,
)

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_load_unload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test load and unload."""
    aioclient_mock.get(
        URL_VEHICLES,
        text=TEST_VEHICLES,
    )
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_auth_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test init with an authentication failure."""

    aioclient_mock.get(
        URL_VEHICLES,
        exc=ERROR_AUTH,
    )
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unknown_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test init with an authentication failure."""
    aioclient_mock.get(
        URL_VEHICLES,
        exc=ERROR_UNKNOWN,
    )
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_connection_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test init with a network connection failure."""
    aioclient_mock.get(
        URL_VEHICLES,
        exc=ERROR_CONNECTION,
    )
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
