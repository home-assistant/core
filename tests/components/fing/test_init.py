"""Test the Fing integration init."""

from unittest.mock import MagicMock

import httpx
import pytest

from homeassistant.components.fing.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import AsyncMock
from tests.conftest import MockConfigEntry


@pytest.mark.parametrize("api_type", ["new", "old"])
async def test_setup_entry_new_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_fing_agent: AsyncMock,
    api_type: str,
) -> None:
    """Test setup Fing Agent /w New API."""
    entry = await init_integration(hass, mock_config_entry, mocked_fing_agent)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    if api_type == "new":
        assert entry.state is ConfigEntryState.LOADED
    elif api_type == "old":
        assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_fing_agent: AsyncMock,
) -> None:
    """Test that HTTP 401 results in setup error and starts reauth."""
    mocked_fing_agent.get_devices.side_effect = httpx.HTTPStatusError(
        "HTTP status error - 401", request=None, response=httpx.Response(401)
    )
    mock_config_entry.async_start_reauth = MagicMock()

    entry = await init_integration(hass, mock_config_entry, mocked_fing_agent)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    mock_config_entry.async_start_reauth.assert_called_once_with(hass)


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_fing_agent: AsyncMock,
) -> None:
    """Test unload of entry."""
    entry = await init_integration(hass, mock_config_entry, mocked_fing_agent)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
