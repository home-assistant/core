"""Test the Aussie Broadband init."""
from http import HTTPStatus

from aiohttp import ClientConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import RETURN_BADAUTH, URL, setup_platform

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_unload(hass: HomeAssistant) -> None:
    """Test unload."""
    entry = await setup_platform(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_auth_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test init with an authentication failure."""

    aioclient_mock.post(
        URL,
        text=RETURN_BADAUTH,
        status=HTTPStatus.FORBIDDEN,
    )

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_net_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test init with a network failure."""
    aioclient_mock.post(
        URL,
        side_effect=ClientConnectionError,
    )

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR
