"""Test setup and unload of the BirdNET-Go integration."""

from unittest.mock import AsyncMock

from aiobirdnetgo import (
    BirdNetGoAuthenticationError,
    BirdNetGoConnectionError,
    BirdNetGoError,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_birdnet_client: AsyncMock,
) -> None:
    """Test successful setup and unload of a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED


async def test_setup_entry_with_api_key(
    hass: HomeAssistant,
    mock_birdnet_client: AsyncMock,
) -> None:
    """Test setup with optional API key."""
    entry = MockConfigEntry(
        domain="birdnet_go",
        title="BirdNET-Go (192.168.1.100:8080)",
        unique_id="192.168.1.100:8080",
        data={
            "host": "192.168.1.100",
            "port": 8080,
            "ssl": False,
            "api_key": "my_secret_token",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED
    assert entry.runtime_data is not None


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_birdnet_client: AsyncMock,
) -> None:
    """Test config entry setup with authentication failure."""
    mock_birdnet_client.get_kpis.side_effect = BirdNetGoAuthenticationError(
        "Invalid token"
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_birdnet_client: AsyncMock,
) -> None:
    """Test config entry setup with connection failure."""
    mock_birdnet_client.get_kpis.side_effect = BirdNetGoConnectionError(
        "Cannot reach host"
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_generic_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_birdnet_client: AsyncMock,
) -> None:
    """Test config entry setup with generic BirdNET-Go error."""
    mock_birdnet_client.get_kpis.side_effect = BirdNetGoError("General error")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
