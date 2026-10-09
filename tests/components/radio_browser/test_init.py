"""Tests for the Radio Browser integration setup."""

from unittest.mock import patch

from radios import RadioBrowserConnectionError

from homeassistant.components.radio_browser.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and unloading the integration."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.radio_browser.RadioBrowser",
        autospec=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup is retried, with a translated reason, when the API is down."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.radio_browser.RadioBrowser",
        autospec=True,
    ) as mock_browser:
        mock_browser.return_value.stats.side_effect = RadioBrowserConnectionError
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_domain == DOMAIN
    assert mock_config_entry.error_reason_translation_key == "cannot_connect"
