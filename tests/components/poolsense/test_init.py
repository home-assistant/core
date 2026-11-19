"""Tests for the PoolSense integration setup."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_setup_invalid_auth(
    hass: HomeAssistant,
    mock_poolsense_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails with invalid credentials."""
    mock_poolsense_client.test_poolsense_credentials.return_value = False

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == "Invalid authentication"


@pytest.mark.parametrize("exception", [ClientError, TimeoutError])
async def test_setup_cannot_connect(
    hass: HomeAssistant,
    mock_poolsense_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
) -> None:
    """Test setup is retried when PoolSense cannot be reached."""
    mock_poolsense_client.test_poolsense_credentials.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.reason == "Failed to connect to PoolSense"
