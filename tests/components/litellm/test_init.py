"""Tests for the LiteLLM integration setup."""

from unittest.mock import MagicMock

from litellm.proxy.client.exceptions import UnauthorizedError
import pytest
import requests

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (UnauthorizedError("invalid key"), ConfigEntryState.SETUP_ERROR),
        (requests.ConnectionError("no route to host"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_proxy_client: MagicMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test that setup handles errors validating the connection."""
    mock_proxy_client.return_value.models.list.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state
