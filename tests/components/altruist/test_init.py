"""Test the Altruist Sensor integration."""

from unittest.mock import patch

from altruistclient import AltruistError

from homeassistant.components.altruist.const import DOMAIN
from homeassistant.components.altruist.coordinator import AltruistDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Confirm that the runtime_data contains a coordinator
    coordinator = mock_config_entry.runtime_data
    assert isinstance(coordinator, AltruistDataUpdateCoordinator)

    # Confirm that coordinator.client is the mock client
    assert coordinator.client == mock_altruist_client

    # Confirm that the domain is properly set up
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


async def test_setup_entry_client_creation_failure(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test setup failure when client creation fails."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.altruist.coordinator.AltruistClient.from_ip_address",
        side_effect=AltruistError("Connection failed"),
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_fetch_data_failure(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test setup failure when initial data fetch fails."""
    mock_config_entry.add_to_hass(hass)
    mock_altruist_client.fetch_data.side_effect = Exception("Fetch failed")

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test unloading of config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Now test unloading
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
