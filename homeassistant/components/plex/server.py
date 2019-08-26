"""Shared function to create Plex server instances."""
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from .const import CONF_SERVER


def setup_plex_server(server_config):
    """Connect to Plex and return server object.

    Expects one of:
        token + (server_name)
        url + (token) + verify_ssl
    """
    from plexapi.myplex import MyPlexAccount
    from plexapi.server import PlexServer
    from requests import Session
    from .errors import NoServersFound, ServerNotSpecified

    url = server_config.get(CONF_URL)
    token = server_config.get(CONF_TOKEN)
    server_name = server_config.get(CONF_SERVER)
    verify_ssl = server_config.get(CONF_VERIFY_SSL)

    plex_server = None
    if url:
        session = None
        if url.startswith("https") and not verify_ssl:
            session = Session()
            session.verify = False
        plex_server = PlexServer(url, token, session)
    elif token:
        account = MyPlexAccount(token=token)
        available_servers = [
            x.name for x in account.resources() if "server" in x.provides
        ]

        if not available_servers:
            raise NoServersFound
        if not server_name and len(available_servers) > 1:
            raise ServerNotSpecified(available_servers)
        server_choice = server_name if server_name else available_servers[0]
        plex_server = account.resource(server_choice).connect()
    return plex_server
