"""Some recurrend functions used in the qtorrent components."""
import logging

from qbittorrent.client import Client, LoginRequired
from requests.exceptions import RequestException

_LOGGER = logging.getLogger(__name__)


def get_main_data_client(client: Client):
    """Get the main data from the Qtorrent client."""
    return client.sync_main_data()


def create_client(url, username, password):
    """Create the Qtorrent client."""
    errors = {}
    try:
        client = Client(url)
        client.login(username, password)
        return client
    except LoginRequired:
        errors["base"] = "invalid_auth"
        return errors
    except RequestException as err:
        errors["base"] = "cannot_connect"
        _LOGGER.error("Connection failed - %s", err)
        return errors


def retrieve_torrentdata(client: Client, torrentfilter):
    """Retrieve torrent data from the Qtorrent client with specific filters."""
    return client.torrents(filter=torrentfilter)
