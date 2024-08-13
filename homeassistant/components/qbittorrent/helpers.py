"""Helper functions for qBittorrent."""

from datetime import UTC, datetime
from typing import Any, cast

from qbittorrentapi import Client, TorrentDictionary, TorrentInfoList


def setup_client(url: str, username: str, password: str, verify_ssl: bool) -> Client:
    """Create a qBittorrent client."""
    client = Client(
        url, username=username, password=password, VERIFY_WEBUI_CERTIFICATE=verify_ssl
    )
    client.auth_log_in(username, password)
    return client


def seconds_to_hhmmss(seconds) -> str:
    """Convert seconds to HH:MM:SS format."""
    if seconds == 8640000:
        return "None"

    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"


def format_unix_timestamp(timestamp) -> str:
    """Format a UNIX timestamp to a human-readable date."""
    dt_object = datetime.fromtimestamp(timestamp, tz=UTC)
    return dt_object.isoformat()


def format_progress(torrent: TorrentDictionary) -> str:
    """Format the progress of a torrent."""
    progress = cast(float, torrent["progress"]) * 100
    return f"{progress:.2f}"


def format_torrents(
    torrents: TorrentInfoList,
) -> dict[str, dict[str, Any]]:
    """Format a list of torrents."""
    value = {}
    for torrent in torrents:
        value[str(torrent["name"])] = format_torrent(torrent)

    return value


def format_torrent(torrent: TorrentDictionary) -> dict[str, Any]:
    """Format a single torrent."""
    value = {}
    value["id"] = torrent["hash"]
    value["added_date"] = format_unix_timestamp(torrent["added_on"])
    value["percent_done"] = format_progress(torrent)
    value["status"] = torrent["state"]
    value["eta"] = seconds_to_hhmmss(torrent["eta"])
    ratio = cast(float, torrent["ratio"])
    value["ratio"] = f"{ratio:.2f}"

    return value
