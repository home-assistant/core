"""Provide common fixtures for downloader tests."""

import asyncio
from pathlib import Path

import pytest
from requests_mock import Mocker

from homeassistant.components.downloader.const import (
    CONF_DOWNLOAD_DIR,
    DOMAIN,
    DOWNLOAD_COMPLETED_EVENT,
    DOWNLOAD_FAILED_EVENT,
)
from homeassistant.core import Event, HomeAssistant, callback

from tests.common import MockConfigEntry


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the downloader integration for testing."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant,
    download_dir: Path,
) -> MockConfigEntry:
    """Return a mocked config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DOWNLOAD_DIR: str(download_dir)},
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def download_dir(tmp_path: Path) -> Path:
    """Return a download directory."""
    return tmp_path


@pytest.fixture(autouse=True)
def mock_download_request(
    requests_mock: Mocker,
    download_url: str,
) -> None:
    """Mock the download request."""
    requests_mock.get(download_url, text="{'one': 1}")


@pytest.fixture
def download_url() -> str:
    """Return a mock download URL."""
    return "http://example.com/file.txt"


@pytest.fixture
def download_completed(hass: HomeAssistant) -> asyncio.Event:
    """Return an asyncio event to wait for download completion."""
    download_event = asyncio.Event()

    @callback
    def download_set(event: Event[dict[str, str]]) -> None:
        """Set the event when download is completed."""
        download_event.set()

    hass.bus.async_listen_once(f"{DOMAIN}_{DOWNLOAD_COMPLETED_EVENT}", download_set)

    return download_event


@pytest.fixture
def download_failed(hass: HomeAssistant) -> asyncio.Event:
    """Return an asyncio event to wait for download failure."""
    download_event = asyncio.Event()

    @callback
    def download_set(event: Event[dict[str, str]]) -> None:
        """Set the event when download has failed."""
        download_event.set()

    hass.bus.async_listen_once(f"{DOMAIN}_{DOWNLOAD_FAILED_EVENT}", download_set)

    return download_event
