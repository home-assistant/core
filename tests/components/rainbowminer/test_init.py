"""Test the RainbowMiner integration setup."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry
from rainbowminer_api_client import RainbowMinerAuthError, RainbowMinerConnectionError

from homeassistant.components.rainbowminer.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import TEST_HOST, TEST_PORT


async def test_setup_unload(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup and unload of the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_with_auth(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
) -> None:
    """Test setup with username and password."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        },
    )
    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the version request fails."""
    mock_rainbowminer_client.get_version.side_effect = RainbowMinerConnectionError(
        "Connection refused"
    )
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_error_on_invalid_auth(
    hass: HomeAssistant,
    mock_rainbowminer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails on invalid auth."""
    mock_rainbowminer_client.get_version.side_effect = RainbowMinerAuthError(
        "Unauthorized"
    )
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
