"""Tests for the downloader component init."""

from homeassistant.components.downloader.const import DOMAIN, SERVICE_DOWNLOAD_FILE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_initialization(
    hass: HomeAssistant, loaded_config_entry: MockConfigEntry
) -> None:
    """Test the initialization of the downloader component."""

    assert hass.services.has_service(DOMAIN, SERVICE_DOWNLOAD_FILE)
    assert loaded_config_entry.state is ConfigEntryState.LOADED
