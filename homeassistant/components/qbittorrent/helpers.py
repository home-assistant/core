"""Helper functions for qBittorrent."""
import qbittorrentapi


def setup_client(
    url: str, username: str, password: str, verify_ssl: bool
) -> qbittorrentapi.Client:
    """Create a qBittorrent client."""

    client = qbittorrentapi.Client(
        url, username=username, password=password, VERIFY_WEBUI_CERTIFICATE=verify_ssl
    )
    client.auth_log_in(username, password)
    return client
