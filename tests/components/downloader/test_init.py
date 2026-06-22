"""Tests for the downloader component init."""

from pathlib import Path

import pytest

from homeassistant.components.downloader.const import (
    CONF_DOWNLOAD_DIR,
    DOMAIN,
    SERVICE_DOWNLOAD_FILE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def download_dir(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    """Return a download directory."""
    if hasattr(request, "param"):
        return tmp_path / request.param
    return tmp_path


async def test_config_entry_setup(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test config entry setup."""
    config_entry = setup_integration

    assert hass.services.has_service(DOMAIN, SERVICE_DOWNLOAD_FILE)
    assert config_entry.state is ConfigEntryState.LOADED


async def test_config_entry_setup_relative_directory(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test config entry setup with a relative download directory."""
    relative_directory = "downloads"
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_DOWNLOAD_DIR: relative_directory},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # The config entry will fail to set up since the directory does not exist.
    # This is not relevant for this test.
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.data[CONF_DOWNLOAD_DIR] == hass.config.path(
        relative_directory
    )


@pytest.mark.parametrize(
    "download_dir",
    [
        "not_existing_path",
    ],
    indirect=True,
)
async def test_config_entry_setup_not_existing_directory(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry setup without existing download directory."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert not hass.services.has_service(DOMAIN, SERVICE_DOWNLOAD_FILE)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
