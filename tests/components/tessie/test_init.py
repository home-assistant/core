"""Test the Tessie init."""

from http import HTTPStatus

from aiohttp import ClientConnectionError, ClientResponseError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_unload(hass: HomeAssistant) -> None:
    """Test unload."""
    entry = await setup_platform(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_auth_failure(hass: HomeAssistant) -> None:
    """Test init with an authentication failure."""
    entry = await setup_platform(
        hass,
        side_effect=ClientResponseError(
            request_info=None, history=None, status=HTTPStatus.UNAUTHORIZED
        ),
    )
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unknown_failure(hass: HomeAssistant) -> None:
    """Test init with an authentication failure."""
    entry = await setup_platform(
        hass,
        side_effect=ClientResponseError(
            request_info=None, history=None, status=HTTPStatus.BAD_REQUEST
        ),
    )
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_net_failure(hass: HomeAssistant) -> None:
    """Test init with a network failure."""
    entry = await setup_platform(hass, side_effect=ClientConnectionError())
    assert entry.state is ConfigEntryState.SETUP_RETRY
