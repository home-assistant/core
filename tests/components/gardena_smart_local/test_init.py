"""Tests for the GARDENA smart local integration setup."""

from unittest.mock import MagicMock, patch

import aiohttp

from homeassistant.components.gardena_smart_local.const import DEFAULT_PORT, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_PASSWORD: "testpassword",
}


async def test_setup_rejected_password_is_auth_error(hass: HomeAssistant) -> None:
    """A gateway 401 during setup fails the entry instead of retrying forever."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.WSServerHandshakeError(
            request_info=MagicMock(), history=(), status=401, message="Unauthorized"
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_gateway_offline_is_retried(hass: HomeAssistant) -> None:
    """A connection failure during setup keeps the entry in retry state."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.ClientConnectionError("Connection refused"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
