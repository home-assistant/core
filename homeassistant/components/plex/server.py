"""Shared class to maintain Plex server instances."""
import logging
import ssl
import time
from urllib.parse import urlparse

from plexapi.exceptions import BadRequest, NotFound, Unauthorized
import plexapi.myplex
import plexapi.playqueue
import plexapi.server
from requests import Session
import requests.exceptions

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_VIDEO,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_IGNORE_NEW_SHARED_USERS,
    CONF_IGNORE_PLEX_WEB_CLIENTS,
    CONF_MONITORED_USERS,
    CONF_SERVER,
    CONF_USE_EPISODE_ART,
    DEBOUNCE_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLAYER_SOURCE,
    PLEX_NEW_MP_SIGNAL,
    PLEX_UPDATE_MEDIA_PLAYER_SIGNAL,
    PLEX_UPDATE_SENSOR_SIGNAL,
    PLEXTV_THROTTLE,
    X_PLEX_DEVICE_NAME,
    X_PLEX_PLATFORM,
    X_PLEX_PRODUCT,
    X_PLEX_VERSION,
)
from .errors import NoServersFound, ServerNotSpecified, ShouldUpdateConfigEntry

_LOGGER = logging.getLogger(__name__)

# Set default headers sent by plexapi
plexapi.X_PLEX_DEVICE_NAME = X_PLEX_DEVICE_NAME
plexapi.X_PLEX_PLATFORM = X_PLEX_PLATFORM
plexapi.X_PLEX_PRODUCT = X_PLEX_PRODUCT
plexapi.X_PLEX_VERSION = X_PLEX_VERSION


class PlexServer:
    """Manages a single Plex server connection."""

    def __init__(self, hass, server_config, known_server_id=None, options=None):
        """Initialize a Plex server instance."""
        self.hass = hass
        self._plex_account = None
        self._plex_server = None
        self._created_clients = set()
        self._known_clients = set()
        self._known_idle = set()
        self._url = server_config.get(CONF_URL)
        self._token = server_config.get(CONF_TOKEN)
        self._server_name = server_config.get(CONF_SERVER)
        self._verify_ssl = server_config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
        self._server_id = known_server_id
        self.options = options
        self.server_choice = None
        self._accounts = []
        self._owner_username = None
        self._plextv_clients = None
        self._plextv_client_timestamp = 0
        self._plextv_device_cache = {}
        self._use_plex_tv = self._token is not None
        self._version = None
        self.async_update_platforms = Debouncer(
            hass,
            _LOGGER,
            cooldown=DEBOUNCE_TIMEOUT,
            immediate=True,
            function=self._async_update_platforms,
        ).async_call

        # Header conditionally added as it is not available in config entry v1
        if CONF_CLIENT_ID in server_config:
            plexapi.X_PLEX_IDENTIFIER = server_config[CONF_CLIENT_ID]
        plexapi.myplex.BASE_HEADERS = plexapi.reset_base_headers()
        plexapi.server.BASE_HEADERS = plexapi.reset_base_headers()

    @property
    def account(self):
        """Return a MyPlexAccount instance."""
        if not self._plex_account and self._use_plex_tv:
            try:
                self._plex_account = plexapi.myplex.MyPlexAccount(token=self._token)
            except (BadRequest, Unauthorized):
                self._use_plex_tv = False
                _LOGGER.error("Not authorized to access plex.tv with provided token")
                raise
        return self._plex_account

    def plextv_clients(self):
        """Return available clients linked to Plex account."""
        if self.account is None:
            return []

        now = time.time()
        if now - self._plextv_client_timestamp > PLEXTV_THROTTLE:
            self._plextv_client_timestamp = now
            self._plextv_clients = [
                x
                for x in self.account.resources()
                if "player" in x.provides and x.presence
            ]
            _LOGGER.debug(
                "Current available clients from plex.tv: %s", self._plextv_clients
            )
        return self._plextv_clients

    def connect(self):
        """Connect to a Plex server directly, obtaining direct URL if necessary."""
        config_entry_update_needed = False

        def _connect_with_token():
            available_servers = [
                (x.name, x.clientIdentifier)
                for x in self.account.resources()
                if "server" in x.provides
            ]

            if not available_servers:
                raise NoServersFound
            if not self._server_name and len(available_servers) > 1:
                raise ServerNotSpecified(available_servers)

            self.server_choice = (
                self._server_name if self._server_name else available_servers[0][0]
            )
            self._plex_server = self.account.resource(self.server_choice).connect(
                timeout=10
            )

        def _connect_with_url():
            session = None
            if self._url.startswith("https") and not self._verify_ssl:
                session = Session()
                session.verify = False
            self._plex_server = plexapi.server.PlexServer(
                self._url, self._token, session
            )

        def _update_plexdirect_hostname():
            matching_servers = [
                x.name
                for x in self.account.resources()
                if x.clientIdentifier == self._server_id
            ]
            if matching_servers:
                self._plex_server = self.account.resource(matching_servers[0]).connect(
                    timeout=10
                )
                return True
            _LOGGER.error("Attempt to update plex.direct hostname failed")
            return False

        if self._url:
            try:
                _connect_with_url()
            except requests.exceptions.SSLError as error:
                while error and not isinstance(error, ssl.SSLCertVerificationError):
                    error = error.__context__  # pylint: disable=no-member
                if isinstance(error, ssl.SSLCertVerificationError):
                    domain = urlparse(self._url).netloc.split(":")[0]
                    if domain.endswith("plex.direct") and error.args[0].startswith(
                        f"hostname '{domain}' doesn't match"
                    ):
                        _LOGGER.warning(
                            "Plex SSL certificate's hostname changed, updating"
                        )
                        if _update_plexdirect_hostname():
                            config_entry_update_needed = True
                        else:
                            raise Unauthorized(
                                "New certificate cannot be validated with provided token"
                            )
                    else:
                        raise
                else:
                    raise
        else:
            _connect_with_token()

        try:
            system_accounts = self._plex_server.systemAccounts()
        except Unauthorized:
            _LOGGER.warning(
                "Plex account has limited permissions, shared account filtering will not be available"
            )
        else:
            self._accounts = [
                account.name for account in system_accounts if account.name
            ]
            _LOGGER.debug("Linked accounts: %s", self.accounts)

            owner_account = [
                account.name for account in system_accounts if account.accountID == 1
            ]
            if owner_account:
                self._owner_username = owner_account[0]
                _LOGGER.debug("Server owner found: '%s'", self._owner_username)

        self._version = self._plex_server.version

        if config_entry_update_needed:
            raise ShouldUpdateConfigEntry

    @callback
    def async_refresh_entity(self, machine_identifier, device, session):
        """Forward refresh dispatch to media_player."""
        unique_id = f"{self.machine_identifier}:{machine_identifier}"
        _LOGGER.debug("Refreshing %s", unique_id)
        async_dispatcher_send(
            self.hass,
            PLEX_UPDATE_MEDIA_PLAYER_SIGNAL.format(unique_id),
            device,
            session,
        )

    def _fetch_platform_data(self):
        """Fetch all data from the Plex server in a single method."""
        return (
            self._plex_server.clients(),
            self._plex_server.sessions(),
            self.plextv_clients(),
        )

    async def _async_update_platforms(self):
        """Update the platform entities."""
        _LOGGER.debug("Updating devices")

        available_clients = {}
        ignored_clients = set()
        new_clients = set()

        monitored_users = self.accounts
        known_accounts = set(self.option_monitored_users)
        if known_accounts:
            monitored_users = {
                user
                for user in self.option_monitored_users
                if self.option_monitored_users[user]["enabled"]
            }

        if not self.option_ignore_new_shared_users:
            for new_user in self.accounts - known_accounts:
                monitored_users.add(new_user)

        try:
            devices, sessions, plextv_clients = await self.hass.async_add_executor_job(
                self._fetch_platform_data
            )
        except (
            plexapi.exceptions.BadRequest,
            requests.exceptions.RequestException,
        ) as ex:
            _LOGGER.error(
                "Could not connect to Plex server: %s (%s)", self.friendly_name, ex
            )
            return

        def process_device(source, device):
            self._known_idle.discard(device.machineIdentifier)
            available_clients.setdefault(device.machineIdentifier, {"device": device})
            available_clients[device.machineIdentifier].setdefault(
                PLAYER_SOURCE, source
            )

            if device.machineIdentifier not in ignored_clients:
                if self.option_ignore_plexweb_clients and device.product == "Plex Web":
                    ignored_clients.add(device.machineIdentifier)
                    if device.machineIdentifier not in self._known_clients:
                        _LOGGER.debug(
                            "Ignoring %s %s: %s",
                            "Plex Web",
                            source,
                            device.machineIdentifier,
                        )
                    return

            if device.machineIdentifier not in (
                self._created_clients | ignored_clients | new_clients
            ):
                new_clients.add(device.machineIdentifier)
                _LOGGER.debug(
                    "New %s from %s: %s",
                    device.product,
                    source,
                    device.machineIdentifier,
                )

        for device in devices:
            process_device("PMS", device)

        def connect_to_resource(resource):
            """Connect to a plex.tv resource and return a Plex client."""
            client_id = resource.clientIdentifier
            if client_id in self._plextv_device_cache:
                return self._plextv_device_cache[client_id]

            client = None
            try:
                client = resource.connect(timeout=3)
                _LOGGER.debug("plex.tv resource connection successful: %s", client)
            except NotFound:
                _LOGGER.error("plex.tv resource connection failed: %s", resource.name)

            self._plextv_device_cache[client_id] = client
            return client

        for plextv_client in plextv_clients:
            if plextv_client.clientIdentifier not in available_clients:
                device = await self.hass.async_add_executor_job(
                    connect_to_resource, plextv_client
                )
                if device:
                    process_device("plex.tv", device)

        for session in sessions:
            if session.TYPE == "photo":
                _LOGGER.debug("Photo session detected, skipping: %s", session)
                continue

            session_username = session.usernames[0]
            for player in session.players:
                if session_username and session_username not in monitored_users:
                    ignored_clients.add(player.machineIdentifier)
                    _LOGGER.debug(
                        "Ignoring %s client owned by '%s'",
                        player.product,
                        session_username,
                    )
                    continue
                process_device("session", player)
                available_clients[player.machineIdentifier]["session"] = session

        new_entity_configs = []
        for client_id, client_data in available_clients.items():
            if client_id in ignored_clients:
                continue
            if client_id in new_clients:
                new_entity_configs.append(client_data)
                self._created_clients.add(client_id)
            else:
                self.async_refresh_entity(
                    client_id, client_data["device"], client_data.get("session")
                )

        self._known_clients.update(new_clients | ignored_clients)

        idle_clients = (
            self._known_clients - self._known_idle - ignored_clients
        ).difference(available_clients)
        for client_id in idle_clients:
            self.async_refresh_entity(client_id, None, None)
            self._known_idle.add(client_id)
            self._plextv_device_cache.pop(client_id, None)

        if new_entity_configs:
            async_dispatcher_send(
                self.hass,
                PLEX_NEW_MP_SIGNAL.format(self.machine_identifier),
                new_entity_configs,
            )

        async_dispatcher_send(
            self.hass,
            PLEX_UPDATE_SENSOR_SIGNAL.format(self.machine_identifier),
            sessions,
        )

    @property
    def plex_server(self):
        """Return the plexapi PlexServer instance."""
        return self._plex_server

    @property
    def accounts(self):
        """Return accounts associated with the Plex server."""
        return set(self._accounts)

    @property
    def owner(self):
        """Return the Plex server owner username."""
        return self._owner_username

    @property
    def version(self):
        """Return the version of the Plex server."""
        return self._version

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
    def option_ignore_new_shared_users(self):
        """Return ignore_new_shared_users option."""
        return self.options[MP_DOMAIN].get(CONF_IGNORE_NEW_SHARED_USERS, False)

    @property
    def option_use_episode_art(self):
        """Return use_episode_art option."""
        return self.options[MP_DOMAIN].get(CONF_USE_EPISODE_ART, False)

    @property
    def option_monitored_users(self):
        """Return dict of monitored users option."""
        return self.options[MP_DOMAIN].get(CONF_MONITORED_USERS, {})

    @property
    def option_ignore_plexweb_clients(self):
        """Return ignore_plex_web_clients option."""
        return self.options[MP_DOMAIN].get(CONF_IGNORE_PLEX_WEB_CLIENTS, False)

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

    def fetch_item(self, item):
        """Fetch item from Plex server."""
        return self._plex_server.fetchItem(item)

    def lookup_media(self, media_type, **kwargs):
        """Lookup a piece of media."""
        media_type = media_type.lower()

        if media_type == DOMAIN:
            key = kwargs["plex_key"]
            try:
                return self.fetch_item(key)
            except NotFound:
                _LOGGER.error("Media for key %s not found", key)
                return None

        if media_type == MEDIA_TYPE_PLAYLIST:
            try:
                playlist_name = kwargs["playlist_name"]
                return self.playlist(playlist_name)
            except KeyError:
                _LOGGER.error("Must specify 'playlist_name' for this search")
                return None
            except NotFound:
                _LOGGER.error(
                    "Playlist '%s' not found", playlist_name,
                )
                return None

        try:
            library_name = kwargs["library_name"]
            library_section = self.library.section(library_name)
        except KeyError:
            _LOGGER.error("Must specify 'library_name' for this search")
            return None
        except NotFound:
            _LOGGER.error("Library '%s' not found", library_name)
            return None

        def lookup_music():
            """Search for music and return a Plex media object."""
            album_name = kwargs.get("album_name")
            track_name = kwargs.get("track_name")
            track_number = kwargs.get("track_number")

            try:
                artist_name = kwargs["artist_name"]
                artist = library_section.get(artist_name)
            except KeyError:
                _LOGGER.error("Must specify 'artist_name' for this search")
                return None
            except NotFound:
                _LOGGER.error(
                    "Artist '%s' not found in '%s'", artist_name, library_name
                )
                return None

            if album_name:
                try:
                    album = artist.album(album_name)
                except NotFound:
                    _LOGGER.error(
                        "Album '%s' by '%s' not found", album_name, artist_name
                    )
                    return None

                if track_name:
                    try:
                        return album.track(track_name)
                    except NotFound:
                        _LOGGER.error(
                            "Track '%s' on '%s' by '%s' not found",
                            track_name,
                            album_name,
                            artist_name,
                        )
                        return None

                if track_number:
                    for track in album.tracks():
                        if int(track.index) == int(track_number):
                            return track

                    _LOGGER.error(
                        "Track %d on '%s' by '%s' not found",
                        track_number,
                        album_name,
                        artist_name,
                    )
                    return None
                return album

            if track_name:
                try:
                    return artist.get(track_name)
                except NotFound:
                    _LOGGER.error(
                        "Track '%s' by '%s' not found", track_name, artist_name
                    )
                    return None

            return artist

        def lookup_tv():
            """Find TV media and return a Plex media object."""
            season_number = kwargs.get("season_number")
            episode_number = kwargs.get("episode_number")

            try:
                show_name = kwargs["show_name"]
                show = library_section.get(show_name)
            except KeyError:
                _LOGGER.error("Must specify 'show_name' for this search")
                return None
            except NotFound:
                _LOGGER.error("Show '%s' not found in '%s'", show_name, library_name)
                return None

            if not season_number:
                return show

            try:
                season = show.season(int(season_number))
            except NotFound:
                _LOGGER.error(
                    "Season %d of '%s' not found", season_number, show_name,
                )
                return None

            if not episode_number:
                return season

            try:
                return season.episode(episode=int(episode_number))
            except NotFound:
                _LOGGER.error(
                    "Episode not found: %s - S%sE%s",
                    show_name,
                    str(season_number).zfill(2),
                    str(episode_number).zfill(2),
                )
                return None

        if media_type == MEDIA_TYPE_MUSIC:
            return lookup_music()
        if media_type == MEDIA_TYPE_EPISODE:
            return lookup_tv()
        if media_type == MEDIA_TYPE_VIDEO:
            try:
                video_name = kwargs["video_name"]
                return library_section.get(video_name)
            except KeyError:
                _LOGGER.error("Must specify 'video_name' for this search")
            except NotFound:
                _LOGGER.error(
                    "Movie '%s' not found in '%s'", video_name, library_name,
                )
