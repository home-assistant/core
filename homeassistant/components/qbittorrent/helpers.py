"""Helper functions for qBittorrent."""
from qbittorrent.client import Client


def setup_client(url: str, username: str, password: str, verify_ssl: bool) -> Client:
    """Create a qBittorrent client."""
    client = Client(url, verify=verify_ssl)
    client.login(username, password)
    # Get an arbitrary attribute to test if connection succeeds
    client.get_alternative_speed_status()
    return client
