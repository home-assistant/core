"""Shared class to maintain Plex server instances."""
import logging

import plexapi.myplex
import plexapi.playqueue
import plexapi.server
from requests import Session
import requests.exceptions

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    CONF_CLIENT_IDENTIFIER,
    CONF_SERVER,
    CONF_SHOW_ALL_CONTROLS,
    CONF_USE_EPISODE_ART,
    DEFAULT_VERIFY_SSL,
    PLEX_NEW_MP_SIGNAL,
    PLEX_UPDATE_MEDIA_PLAYER_SIGNAL,
    PLEX_UPDATE_SENSOR_SIGNAL,
    X_PLEX_DEVICE_NAME,
    X_PLEX_PLATFORM,
    X_PLEX_PRODUCT,
    X_PLEX_VERSION,
)
from .errors import NoServersFound, ServerNotSpecified

_LOGGER = logging.getLogger(__name__)

# Set default headers sent by plexapi
plexapi.X_PLEX_DEVICE_NAME = X_PLEX_DEVICE_NAME
plexapi.X_PLEX_PLATFORM = X_PLEX_PLATFORM
plexapi.X_PLEX_PRODUCT = X_PLEX_PRODUCT
plexapi.X_PLEX_VERSION = X_PLEX_VERSION


class PlexServer:
    """Manages a single Plex server connection."""

    def __init__(self, hass, server_config, options=None):
        """Initialize a Plex server instance."""
        self._hass = hass
        self._plex_server = None
        self._known_clients = set()
        self._known_idle = set()
        self._url = server_config.get(CONF_URL)
        self._token = server_config.get(CONF_TOKEN)
        self._server_name = server_config.get(CONF_SERVER)
        self._verify_ssl = server_config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
        self.options = options
        self.server_choice = None

        # Header conditionally added as it is not available in config entry v1
        if CONF_CLIENT_IDENTIFIER in server_config:
            plexapi.X_PLEX_IDENTIFIER = server_config[CONF_CLIENT_IDENTIFIER]
        plexapi.myplex.BASE_HEADERS = plexapi.reset_base_headers()
        plexapi.server.BASE_HEADERS = plexapi.reset_base_headers()

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
            self._plex_server = account.resource(self.server_choice).connect(timeout=10)

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

    def refresh_entity(self, machine_identifier, device, session):
        """Forward refresh dispatch to media_player."""
        unique_id = f"{self.machine_identifier}:{machine_identifier}"
        _LOGGER.debug("Refreshing %s", unique_id)
        dispatcher_send(
            self._hass,
            PLEX_UPDATE_MEDIA_PLAYER_SIGNAL.format(unique_id),
            device,
            session,
        )

    def update_platforms(self):
        """Update the platform entities."""
        _LOGGER.debug("Updating devices")

        available_clients = {}
        new_clients = set()

        try:
            devices = self._plex_server.clients()
            sessions = self._plex_server.sessions()
        except plexapi.exceptions.BadRequest:
            _LOGGER.exception("Error requesting Plex client data from server")
            return
        except requests.exceptions.RequestException as ex:
            _LOGGER.warning(
                "Could not connect to Plex server: %s (%s)", self.friendly_name, ex
            )
            return

        for device in devices:
            self._known_idle.discard(device.machineIdentifier)
            available_clients[device.machineIdentifier] = {"device": device}

            if device.machineIdentifier not in self._known_clients:
                new_clients.add(device.machineIdentifier)
                _LOGGER.debug("New device: %s", device.machineIdentifier)

        for session in sessions:
            if session.TYPE == "photo":
                _LOGGER.debug("Photo session detected, skipping: %s", session)
                continue
            for player in session.players:
                self._known_idle.discard(player.machineIdentifier)
                available_clients.setdefault(
                    player.machineIdentifier, {"device": player}
                )
                available_clients[player.machineIdentifier]["session"] = session

                if player.machineIdentifier not in self._known_clients:
                    new_clients.add(player.machineIdentifier)
                    _LOGGER.debug("New session: %s", player.machineIdentifier)

        new_entity_configs = []
        for client_id, client_data in available_clients.items():
            if client_id in new_clients:
                new_entity_configs.append(client_data)
            else:
                self.refresh_entity(
                    client_id, client_data["device"], client_data.get("session")
                )

        self._known_clients.update(new_clients)

        idle_clients = (self._known_clients - self._known_idle).difference(
            available_clients
        )
        for client_id in idle_clients:
            self.refresh_entity(client_id, None, None)
            self._known_idle.add(client_id)

        if new_entity_configs:
            dispatcher_send(
                self._hass,
                PLEX_NEW_MP_SIGNAL.format(self.machine_identifier),
                new_entity_configs,
            )

        dispatcher_send(
            self._hass,
            PLEX_UPDATE_SENSOR_SIGNAL.format(self.machine_identifier),
            sessions,
        )

    @property
    def plex_server(self):
        """Return the plexapi PlexServer instance."""
        return self._plex_server

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
        return self._plex_server._baseurl  # pylint: disable=protected-access

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
