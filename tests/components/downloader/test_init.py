"""Tests for the downloader component init."""

from unittest.mock import patch

from homeassistant.components.downloader import (
    CONF_DOWNLOAD_DIR,
    DOMAIN,
    SERVICE_DOWNLOAD_FILE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_initialization(hass: HomeAssistant) -> None:
    """Test the initialization of the downloader component."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DOWNLOAD_DIR: "/test_dir",
        },
    )
    config_entry.add_to_hass(hass)
    with patch("os.path.isdir", return_value=True):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    assert hass.services.has_service(DOMAIN, SERVICE_DOWNLOAD_FILE)
    assert config_entry.state is ConfigEntryState.LOADED


async def test_import(hass: HomeAssistant) -> None:
    """Test the import of the downloader component."""
    with patch("os.path.isdir", return_value=True):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_DOWNLOAD_DIR: "/test_dir",
                },
            },
        )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {CONF_DOWNLOAD_DIR: "/test_dir"}
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service(DOMAIN, SERVICE_DOWNLOAD_FILE)
