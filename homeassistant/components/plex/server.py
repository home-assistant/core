"""Shared function to create Plex server instances."""
from homeassistant.const import (
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from .const import CONF_SERVER

def setup_plex_server(server_config):
    from plexapi.myplex import MyPlexAccount
    from plexapi.server import PlexServer
    from requests import Session
    from .errors import NoServersFound, ServerNotSpecified

    url = server_config.get(CONF_URL)
    token = server_config.get(CONF_TOKEN)
    username = server_config.get(CONF_USERNAME)
    server_name = server_config.get(CONF_SERVER)
    verify_ssl = server_config.get(CONF_VERIFY_SSL)

    plex_server = None
    if username:
        account = MyPlexAccount(username=username, token=token)
        
        if not account.resources():
            raise NoServersFound("No Plex servers linked to this account")
        if not server_name and len(account.resources()) > 1:
            raise ServerNotSpecified("Multiple Plex servers available but selection not provided")
            
        server_choice = server_name if server_name else account.resources()[0].name
        plex_server = account.resource(server_choice).connect()
    else:
        session = None
        if url.startswith("https") and not verify_ssl:
            session = requests.Session()
            session.verify = False
        plex_server = plexapi.server.PlexServer(url, token, session)
    return plex_server