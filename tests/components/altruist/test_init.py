"""Test the Altruist Sensor integration."""

from unittest.mock import patch

from altruistclient import AltruistError
import pytest

from homeassistant.components.altruist.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.altruist.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data == mock_altruist_client

    # Check that the sensor platform was set up
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_setup_entry_client_creation_failure(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test setup failure when client creation fails."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.altruist.AltruistClient.from_ip_address",
        side_effect=AltruistError("Connection failed"),
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_entry_fetch_data_failure(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test setup failure when initial data fetch fails."""
    mock_config_entry.add_to_hass(hass)
    mock_altruist_client.fetch_data.side_effect = Exception("Fetch failed")

    with patch(
        "homeassistant.components.altruist.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test unloading of config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.altruist.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Now test unloading
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED


async def test_setup_entry_platforms_setup(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test that platforms are properly set up."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.altruist.AltruistClient.from_ip_address",
            return_value=mock_altruist_client,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
        ) as mock_forward_setup,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_forward_setup.assert_called_once_with(mock_config_entry, [Platform.SENSOR])


async def test_setup_entry_runtime_data_stored(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test that runtime data is properly stored."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.altruist.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify that the client is stored as runtime data
    assert hasattr(mock_config_entry, "runtime_data")
    assert mock_config_entry.runtime_data == mock_altruist_client


async def test_setup_entry_logging(
    hass: HomeAssistant,
    mock_config_entry,
    mock_altruist_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that errors are properly logged."""
    mock_config_entry.add_to_hass(hass)
    mock_altruist_client.fetch_data.side_effect = Exception("Test error")

    with patch(
        "homeassistant.components.altruist.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert "Error in Altruist setup: Test error" in caplog.text
