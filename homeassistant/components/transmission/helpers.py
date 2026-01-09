"""Helper functions for Transmission."""

from typing import Any

from transmission_rpc.torrent import Torrent


def format_torrent(torrent: Torrent) -> dict[str, Any]:
    """Format a single torrent."""
    value: dict[str, Any] = {}

    value["id"] = torrent.id
    value["name"] = torrent.name
    value["status"] = torrent.status.value
    value["percent_done"] = f"{torrent.percent_done * 100:.2f}%"
    value["ratio"] = f"{torrent.ratio:.2f}"
    value["eta"] = str(torrent.eta) if torrent.eta else None
    value["added_date"] = torrent.added_date.isoformat()
    value["done_date"] = torrent.done_date.isoformat() if torrent.done_date else None
    value["download_dir"] = torrent.download_dir
    value["labels"] = torrent.labels

    return value


def filter_torrents(
    torrents: list[Torrent], statuses: list[str] | None = None
) -> list[Torrent]:
    """Filter torrents based on the statuses provided."""
    return [
        torrent
        for torrent in torrents
        if statuses is None or torrent.status in statuses
    ]


def format_torrents(
    torrents: list[Torrent],
) -> dict[str, dict[str, Any]]:
    """Format a list of torrents."""
    value = {}
    for torrent in torrents:
        value[torrent.name] = format_torrent(torrent)

    return value
