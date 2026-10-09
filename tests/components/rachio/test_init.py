"""Tests for the Rachio integration setup."""

from unittest.mock import MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def _setup_entry(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the config entry with the webhook helpers patched."""
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.rachio.async_get_or_create_registered_webhook_id_and_url",
            return_value="http://example.com/webhook",
        ),
        patch("homeassistant.components.rachio.async_register_webhook"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_setup_authentication_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rachio: MagicMock,
) -> None:
    """Test setup fails when the API key is rejected."""
    mock_rachio.person.info.return_value = ({"status": 401}, {})

    await _setup_entry(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == "Authentication with the Rachio API failed"


async def test_setup_no_devices_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rachio: MagicMock,
) -> None:
    """Test setup fails when the account has no devices."""
    mock_rachio.valve.list_base_stations.return_value = (
        {"status": 200},
        {"baseStations": []},
    )

    await _setup_entry(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == "No Rachio devices found in the account"
