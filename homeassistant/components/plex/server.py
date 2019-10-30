"""Shared class to maintain Plex server instances."""
import plexapi.myplex
import plexapi.playqueue
import plexapi.server
from requests import Session

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL

from .const import (
    CONF_SERVER,
    CONF_SHOW_ALL_CONTROLS,
    CONF_USE_EPISODE_ART,
    DEFAULT_VERIFY_SSL,
    X_PLEX_DEVICE_NAME,
    X_PLEX_PLATFORM,
    X_PLEX_PRODUCT,
    X_PLEX_VERSION,
)
from .errors import NoServersFound, ServerNotSpecified

# Set default headers sent by plexapi
plexapi.X_PLEX_DEVICE_NAME = X_PLEX_DEVICE_NAME
plexapi.X_PLEX_PLATFORM = X_PLEX_PLATFORM
plexapi.X_PLEX_PRODUCT = X_PLEX_PRODUCT
plexapi.X_PLEX_VERSION = X_PLEX_VERSION
plexapi.myplex.BASE_HEADERS = plexapi.reset_base_headers()
plexapi.server.BASE_HEADERS = plexapi.reset_base_headers()


class PlexServer:
    """Manages a single Plex server connection."""

    def __init__(self, server_config, options=None):
        """Initialize a Plex server instance."""
        self._plex_server = None
        self._url = server_config.get(CONF_URL)
        self._token = server_config.get(CONF_TOKEN)
        self._server_name = server_config.get(CONF_SERVER)
        self._verify_ssl = server_config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
        self.options = options
        self.server_choice = None

    def connect(self):
        """Connect to a Plex server directly, obtaining direct URL if necessary."""

        def _connect_with_token():
            account = plexapi.myplex.MyPlexAccount(token=self._token)
            available_servers = [
                (x.name, x.clientIdentifier)
                for x in account.resources()
                if "server" in x.provides
            ]

            if not available_servers:
                raise NoServersFound
            if not self._server_name and len(available_servers) > 1:
                raise ServerNotSpecified(available_servers)

            self.server_choice = (
                self._server_name if self._server_name else available_servers[0][0]
            )
            self._plex_server = account.resource(self.server_choice).connect()

        def _connect_with_url():
            session = None
            if self._url.startswith("https") and not self._verify_ssl:
                session = Session()
                session.verify = False
            self._plex_server = plexapi.server.PlexServer(
                self._url, self._token, session
            )

        if self._url:
            _connect_with_url()
        else:
            _connect_with_token()

    def clients(self):
        """Pass through clients call to plexapi."""
        return self._plex_server.clients()

    def sessions(self):
        """Pass through sessions call to plexapi."""
        return self._plex_server.sessions()

    @property
    def friendly_name(self):
        """Return name of connected Plex server."""
        return self._plex_server.friendlyName

    @property
    def machine_identifier(self):
        """Return unique identifier of connected Plex server."""
        return self._plex_server.machineIdentifier

    @property
    def url_in_use(self):
        """Return URL used for connected Plex server."""
        return self._plex_server._baseurl  # pylint: disable=W0212

    @property
    def use_episode_art(self):
        """Return use_episode_art option."""
        return self.options[MP_DOMAIN][CONF_USE_EPISODE_ART]

    @property
    def show_all_controls(self):
        """Return show_all_controls option."""
        return self.options[MP_DOMAIN][CONF_SHOW_ALL_CONTROLS]

    @property
    def library(self):
        """Return library attribute from server object."""
        return self._plex_server.library

    def playlist(self, title):
        """Return playlist from server object."""
        return self._plex_server.playlist(title)

    def create_playqueue(self, media, **kwargs):
        """Create playqueue on Plex server."""
        return plexapi.playqueue.PlayQueue.create(self._plex_server, media, **kwargs)
