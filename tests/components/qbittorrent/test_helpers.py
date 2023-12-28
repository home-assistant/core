"""Test the qBittorrent helpers."""

from homeassistant.components.qbittorrent.helpers import (
    format_progress,
    format_torrent,
    format_torrents,
    format_unix_timestamp,
    seconds_to_hhmmss,
)
from homeassistant.core import HomeAssistant


async def test_seconds_to_hhmmss(
    hass: HomeAssistant,
) -> None:
    """Test the seconds_to_hhmmss function."""
    assert seconds_to_hhmmss(8640000) == "None"
    assert seconds_to_hhmmss(3661) == "01:01:01"


async def test_format_unix_timestamp(
    hass: HomeAssistant,
) -> None:
    """Test the format_unix_timestamp function."""
    assert format_unix_timestamp(1640995200) == "2022-01-01T00:00:00+0000"


async def test_format_progress(
    hass: HomeAssistant,
) -> None:
    """Test the format_progress function."""
    assert format_progress({"progress": 0.5}) == "50.00"


async def test_format_torrents(
    hass: HomeAssistant,
) -> None:
    """Test the format_torrents function."""
    assert format_torrents([{"name": "torrent1"}, {"name": "torrent2"}]) == {
        "torrent1": {},
        "torrent2": {},
    }


async def test_format_torrent(
    hass: HomeAssistant,
) -> None:
    """Test the format_torrent function."""
    assert format_torrent(
        {
            "hash": "hash1",
            "added_on": 1640995200,
            "progress": 0.5,
            "state": "paused",
            "eta": 86400,
            "ratio": 1.0,
        }
    ) == {
        "id": "hash1",
        "added_date": "2022-01-01T00:00:00+0000",
        "percent_done": "50.00",
        "status": "paused",
        "eta": "24:00:00",
        "ratio": "1.00",
    }
