"""Shared class to maintain Plex server instances."""
import logging

import plexapi.myplex
import plexapi.playqueue
import plexapi.server
from requests import Session
import requests.exceptions

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
from .media_player import PlexMediaPlayer

_LOGGER = logging.getLogger(__name__)

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
        self._clients = {}
        self._sessions = {}
        self._url = server_config.get(CONF_URL)
        self._token = server_config.get(CONF_TOKEN)
        self._server_name = server_config.get(CONF_SERVER)
        self._verify_ssl = server_config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
        self.options = options
        self.add_media_player_callback = None
        self.sensor = None

    def connect(self):
        """Connect to a Plex server directly, obtaining direct URL if necessary."""

        def _set_missing_url():
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

            server_choice = (
                self._server_name if self._server_name else available_servers[0][0]
            )
            connections = account.resource(server_choice).connections
            local_url = [x.httpuri for x in connections if x.local]
            remote_url = [x.uri for x in connections if not x.local]
            self._url = local_url[0] if local_url else remote_url[0]

        def _connect_with_url():
            session = None
            if self._url.startswith("https") and not self._verify_ssl:
                session = Session()
                session.verify = False
            self._plex_server = plexapi.server.PlexServer(
                self._url, self._token, session
            )

        if self._token and not self._url:
            _set_missing_url()

        _connect_with_url()

    def update_platforms(self):
        """Update the platform entities."""
        available_client_ids = []
        new_plex_clients = []

        try:
            devices = self._plex_server.clients()
        except plexapi.exceptions.BadRequest:
            _LOGGER.exception("Error listing plex devices")
            return
        except requests.exceptions.RequestException as ex:
            _LOGGER.warning(
                "Could not connect to Plex server: %s (%s)", self.friendly_name, ex
            )
            return

        for device in devices:
            available_client_ids.append(device.machineIdentifier)

            if device.machineIdentifier not in self._clients:
                new_client = PlexMediaPlayer(
                    self, device, None, self._sessions, self.update_platforms
                )
                self._clients[device.machineIdentifier] = new_client
                _LOGGER.debug("New device: %s", device.machineIdentifier)
                new_plex_clients.append(new_client)
            else:
                _LOGGER.debug("Refreshing device: %s", device.machineIdentifier)
                self._clients[device.machineIdentifier].refresh(device, None)

        try:
            sessions = self._plex_server.sessions()
        except plexapi.exceptions.BadRequest:
            _LOGGER.exception("Error listing Plex sessions")
            return
        except requests.exceptions.RequestException as ex:
            _LOGGER.warning(
                "Could not connect to Plex server: %s (%s)", self.friendly_name, ex
            )
            return

        self._sessions.clear()
        for session in sessions:
            for player in session.players:
                self._sessions[player.machineIdentifier] = session, player

        for machine_identifier, (session, player) in self._sessions.items():
            if machine_identifier in available_client_ids:
                # Avoid using session if already added as a device.
                _LOGGER.debug("Skipping session, device exists: %s", machine_identifier)
                continue

            if (
                machine_identifier not in self._clients
                and machine_identifier is not None
            ):
                new_client = PlexMediaPlayer(
                    self, player, session, self._sessions, self.update_platforms
                )
                self._clients[machine_identifier] = new_client
                _LOGGER.debug("New session: %s", machine_identifier)
                new_plex_clients.append(new_client)
            else:
                _LOGGER.debug("Refreshing session: %s", machine_identifier)
                self._clients[machine_identifier].refresh(None, session)

        for client in self._clients.values():
            # force devices to idle that do not have a valid session
            if client.session is None:
                client.force_idle()

            client.set_availability(
                client.machine_identifier in available_client_ids
                or client.machine_identifier in self._sessions
            )

            if client not in new_plex_clients:
                client.schedule_update_ha_state()

        if new_plex_clients:
            self.add_media_player_callback(  # pylint: disable=not-callable
                new_plex_clients
            )

        self.sensor.sessions = sessions
        self.sensor.schedule_update_ha_state(True)

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
