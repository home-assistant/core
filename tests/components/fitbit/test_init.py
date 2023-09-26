"""Test fitbit component."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus

import pytest

from homeassistant.components.fitbit.const import OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup(
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """Test setting up the integration."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED

    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("token_expiration_time", [12345])
async def test_token_refresh_failure(
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
) -> None:
    """Test where token is expired and the refresh attempt fails and will be retried."""

    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    assert not await integration_setup()
    assert config_entry.state == ConfigEntryState.SETUP_RETRY
