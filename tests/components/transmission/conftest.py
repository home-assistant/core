"""Transmission tests configuration."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from transmission_rpc.session import Session, SessionStats
from transmission_rpc.torrent import Torrent

from homeassistant.components.transmission.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.transmission.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Transmission",
        data={
            CONF_HOST: "0.0.0.0",
            CONF_SSL: False,
            CONF_PATH: "/transmission/rpc",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_PORT: 9091,
        },
        entry_id="01J0BC4QM2YBRP6H5G933AETT7",
        unique_id="bf1c62fe-4941-4332-9886-e54e88dbdba0",
    )


@pytest.fixture
def mock_transmission_client() -> Generator[AsyncMock]:
    """Mock a Transmission client."""
    with (
        patch(
            "transmission_rpc.Client",
            autospec=True,
        ) as mock_client_class,
    ):
        client = mock_client_class.return_value

        session_stats_data = {
            "uploadSpeed": 1,
            "downloadSpeed": 1,
            "activeTorrentCount": 0,
            "pausedTorrentCount": 0,
            "torrentCount": 0,
        }
        client.session_stats.return_value = SessionStats(fields=session_stats_data)

        session_data = {"alt-speed-enabled": False}
        client.get_session.return_value = Session(fields=session_data)

        client.get_torrents.return_value = []

        yield mock_client_class


@pytest.fixture
def mock_torrent():
    """Fixture that returns a factory function to create mock torrents."""

    def _create_mock_torrent(
        torrent_id: int = 1,
        name: str = "Test Torrent",
        percent_done: float = 0.5,
        status: int = 4,
        download_dir: str = "/downloads",
        eta: int = 3600,
        added_date: datetime | None = None,
        ratio: float = 1.5,
    ) -> Torrent:
        """Create a mock torrent with all required attributes."""
        if added_date is None:
            added_date = datetime(2025, 11, 26, 14, 18, 0, tzinfo=UTC)

        torrent_data = {
            "id": torrent_id,
            "name": name,
            "percentDone": percent_done,
            "status": status,
            "rateDownload": 0,
            "rateUpload": 0,
            "downloadDir": download_dir,
            "eta": eta,
            "addedDate": int(added_date.timestamp()),
            "uploadRatio": ratio,
            "error": 0,
            "errorString": "",
        }
        return Torrent(fields=torrent_data)

    return _create_mock_torrent
