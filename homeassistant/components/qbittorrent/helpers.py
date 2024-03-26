"""Helper functions for qBittorrent."""

from qbittorrent.client import Client


def setup_client(
    url: str, username: str, password: str, verify_ssl: bool
) -> tuple[Client, bool]:
    """Create a qBittorrent client."""
    client = Client(url, verify=verify_ssl)
    client.login(username, password)
    # Get an arbitrary attribute to test if connection succeeds
    is_alternative_mode_enabled = bool(client.get_alternative_speed_status())
    return client, is_alternative_mode_enabled
