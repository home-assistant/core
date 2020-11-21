"""Some recurrend functions used in the qtorrent components."""
from qbittorrent.client import Client


def get_main_data_client(client: Client):
    """Get the main data from the Qtorrent client."""
    return client.sync_main_data()


def create_client(url, username, password):
    """Create the Qtorrent client."""
    client = Client(url)
    client.login(username, password)
    return client


def retrieve_torrentdata(client: Client, torrentfilter):
    """Retrieve torrent data from the Qtorrent client with specific filters."""
    return client.torrents(filter=torrentfilter)
