"""
Support to interface with the Plex API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.plex/
"""
from datetime import timedelta
import json
import logging

import requests
import voluptuous as vol

from homeassistant import util
from homeassistant.components.media_player import (
    MEDIA_TYPE_MOVIE, MEDIA_TYPE_MUSIC, MEDIA_TYPE_TVSHOW, PLATFORM_SCHEMA,
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    MediaPlayerDevice)
from homeassistant.const import (
    DEVICE_DEFAULT_NAME, STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.util import dt as dt_util
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['plexapi==3.0.6']

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)

PLEX_CONFIG_FILE = 'plex.conf'
PLEX_DATA = 'plex'

CONF_INCLUDE_NON_CLIENTS = 'include_non_clients'
CONF_USE_EPISODE_ART = 'use_episode_art'
CONF_USE_CUSTOM_ENTITY_IDS = 'use_custom_entity_ids'
CONF_SHOW_ALL_CONTROLS = 'show_all_controls'
CONF_REMOVE_UNAVAILABLE_CLIENTS = 'remove_unavailable_clients'
CONF_CLIENT_REMOVE_INTERVAL = 'client_remove_interval'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_INCLUDE_NON_CLIENTS, default=False): cv.boolean,
    vol.Optional(CONF_USE_EPISODE_ART, default=False): cv.boolean,
    vol.Optional(CONF_USE_CUSTOM_ENTITY_IDS, default=False): cv.boolean,
    vol.Optional(CONF_REMOVE_UNAVAILABLE_CLIENTS, default=True): cv.boolean,
    vol.Optional(CONF_CLIENT_REMOVE_INTERVAL, default=timedelta(seconds=600)):
        vol.All(cv.time_period, cv.positive_timedelta),
})


def setup_platform(hass, config, add_entities_callback, discovery_info=None):
    """Set up the Plex platform."""
    if PLEX_DATA not in hass.data:
        hass.data[PLEX_DATA] = {}

    # get config from plex.conf
    file_config = load_json(hass.config.path(PLEX_CONFIG_FILE))

    if file_config:
        # Setup a configured PlexServer
        host, host_config = file_config.popitem()
        token = host_config['token']
        try:
            has_ssl = host_config['ssl']
        except KeyError:
            has_ssl = False
        try:
            verify_ssl = host_config['verify']
        except KeyError:
            verify_ssl = True

    # Via discovery
    elif discovery_info is not None:
        # Parse discovery data
        host = discovery_info.get('host')
        port = discovery_info.get('port')
        host = '%s:%s' % (host, port)
        _LOGGER.info("Discovered PLEX server: %s", host)

        if host in _CONFIGURING:
            return
        token = None
        has_ssl = False
        verify_ssl = True
    else:
        return

    setup_plexserver(
        host, token, has_ssl, verify_ssl,
        hass, config, add_entities_callback
    )


def setup_plexserver(
        host, token, has_ssl, verify_ssl, hass, config, add_entities_callback):
    """Set up a plexserver based on host parameter."""
    import plexapi.server
    import plexapi.exceptions

    cert_session = None
    http_prefix = 'https' if has_ssl else 'http'
    if has_ssl and (verify_ssl is False):
        _LOGGER.info("Ignoring SSL verification")
        cert_session = requests.Session()
        cert_session.verify = False
    try:
        plexserver = plexapi.server.PlexServer(
            '%s://%s' % (http_prefix, host),
            token, cert_session
        )
        _LOGGER.info("Discovery configuration done (no token needed)")
    except (plexapi.exceptions.BadRequest, plexapi.exceptions.Unauthorized,
            plexapi.exceptions.NotFound) as error:
        _LOGGER.info(error)
        # No token or wrong token
        request_configuration(host, hass, config, add_entities_callback)
        return

    # If we came here and configuring this host, mark as done
    if host in _CONFIGURING:
        request_id = _CONFIGURING.pop(host)
        configurator = hass.components.configurator
        configurator.request_done(request_id)
        _LOGGER.info("Discovery configuration done")

    # Save config
    save_json(
        hass.config.path(PLEX_CONFIG_FILE), {host: {
            'token': token,
            'ssl': has_ssl,
            'verify': verify_ssl,
        }})

    _LOGGER.info('Connected to: %s://%s', http_prefix, host)

    plex_clients = hass.data[PLEX_DATA]
    plex_sessions = {}
    track_utc_time_change(hass, lambda now: update_devices(), second=30)

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_devices():
        """Update the devices objects."""
        try:
            devices = plexserver.clients()
        except plexapi.exceptions.BadRequest:
            _LOGGER.exception("Error listing plex devices")
            return
        except requests.exceptions.RequestException as ex:
            _LOGGER.error(
                "Could not connect to plex server at http://%s (%s)", host, ex)
            return

        new_plex_clients = []
        available_client_ids = []
        for device in devices:
            # For now, let's allow all deviceClass types
            if device.deviceClass in ['badClient']:
                continue

            available_client_ids.append(device.machineIdentifier)

            if device.machineIdentifier not in plex_clients:
                new_client = PlexClient(
                    config, device, None, plex_sessions, update_devices,
                    update_sessions)
                plex_clients[device.machineIdentifier] = new_client
                new_plex_clients.append(new_client)
            else:
                plex_clients[device.machineIdentifier].refresh(device, None)

        # add devices with a session and no client (ex. PlexConnect Apple TV's)
        if config.get(CONF_INCLUDE_NON_CLIENTS):
            for machine_identifier, session in plex_sessions.items():
                if (machine_identifier not in plex_clients
                        and machine_identifier is not None):
                    new_client = PlexClient(
                        config, None, session, plex_sessions, update_devices,
                        update_sessions)
                    plex_clients[machine_identifier] = new_client
                    new_plex_clients.append(new_client)
                else:
                    plex_clients[machine_identifier].refresh(None, session)

        clients_to_remove = []
        for client in plex_clients.values():
            # force devices to idle that do not have a valid session
            if client.session is None:
                client.force_idle()

            client.set_availability(client.machine_identifier
                                    in available_client_ids)

            if not config.get(CONF_REMOVE_UNAVAILABLE_CLIENTS) \
                    or client.available:
                continue

            if (dt_util.utcnow() - client.marked_unavailable) >= \
                    (config.get(CONF_CLIENT_REMOVE_INTERVAL)):
                hass.add_job(client.async_remove())
                clients_to_remove.append(client.machine_identifier)

        while clients_to_remove:
            del plex_clients[clients_to_remove.pop()]

        if new_plex_clients:
            add_entities_callback(new_plex_clients)

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_sessions():
        """Update the sessions objects."""
        try:
            sessions = plexserver.sessions()
        except plexapi.exceptions.BadRequest:
            _LOGGER.exception("Error listing plex sessions")
            return
        except requests.exceptions.RequestException as ex:
            _LOGGER.error(
                "Could not connect to plex server at http://%s (%s)", host, ex)
            return

        plex_sessions.clear()
        for session in sessions:
            for player in session.players:
                plex_sessions[player.machineIdentifier] = session

    update_sessions()
    update_devices()


def request_configuration(host, hass, config, add_entities_callback):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator
    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(_CONFIGURING[host],
                                   'Failed to register, please try again.')

        return

    def plex_configuration_callback(data):
        """Handle configuration changes."""
        setup_plexserver(
            host, data.get('token'),
            cv.boolean(data.get('has_ssl')),
            cv.boolean(data.get('do_not_verify')),
            hass, config, add_entities_callback
        )

    _CONFIGURING[host] = configurator.request_config(
        'Plex Media Server',
        plex_configuration_callback,
        description='Enter the X-Plex-Token',
        entity_picture='/static/images/logo_plex_mediaserver.png',
        submit_caption='Confirm',
        fields=[{
            'id': 'token',
            'name': 'X-Plex-Token',
            'type': ''
        }, {
            'id': 'has_ssl',
            'name': 'Use SSL',
            'type': ''
        }, {
            'id': 'do_not_verify_ssl',
            'name': 'Do not verify SSL',
            'type': ''
        }])


class PlexClient(MediaPlayerDevice):
    """Representation of a Plex device."""

    def __init__(self, config, device, session, plex_sessions,
                 update_devices, update_sessions):
        """Initialize the Plex device."""
        self._app_name = ''
        self._device = None
        self._available = False
        self._marked_unavailable = None
        self._device_protocol_capabilities = None
        self._is_player_active = False
        self._is_player_available = False
        self._player = None
        self._machine_identifier = None
        self._make = ''
        self._name = None
        self._player_state = 'idle'
        self._previous_volume_level = 1  # Used in fake muting
        self._session = None
        self._session_type = None
        self._session_username = None
        self._state = STATE_IDLE
        self._volume_level = 1  # since we can't retrieve remotely
        self._volume_muted = False  # since we can't retrieve remotely
        self.config = config
        self.plex_sessions = plex_sessions
        self.update_devices = update_devices
        self.update_sessions = update_sessions
        # General
        self._media_content_id = None
        self._media_content_rating = None
        self._media_content_type = None
        self._media_duration = None
        self._media_image_url = None
        self._media_title = None
        self._media_position = None
        # Music
        self._media_album_artist = None
        self._media_album_name = None
        self._media_artist = None
        self._media_track = None
        # TV Show
        self._media_episode = None
        self._media_season = None
        self._media_series_title = None

        self.refresh(device, session)

        # Assign custom entity ID if desired
        if self.config.get(CONF_USE_CUSTOM_ENTITY_IDS):
            prefix = ''
            # allow for namespace prefixing when using custom entity names
            if config.get("entity_namespace"):
                prefix = config.get("entity_namespace") + '_'

            # rename the entity id
            if self.machine_identifier:
                self.entity_id = "%s.%s%s" % (
                    'media_player', prefix,
                    self.machine_identifier.lower().replace('-', '_'))
            else:
                if self.name:
                    self.entity_id = "%s.%s%s" % (
                        'media_player', prefix,
                        self.name.lower().replace('-', '_'))

    def _clear_media_details(self):
        """Set all Media Items to None."""
        # General
        self._media_content_id = None
        self._media_content_rating = None
        self._media_content_type = None
        self._media_duration = None
        self._media_image_url = None
        self._media_title = None
        self._media_position = None
        # Music
        self._media_album_artist = None
        self._media_album_name = None
        self._media_artist = None
        self._media_track = None
        # TV Show
        self._media_episode = None
        self._media_season = None
        self._media_series_title = None

        # Clear library Name
        self._app_name = ''

    def refresh(self, device, session):
        """Refresh key device data."""
        # new data refresh
        self._clear_media_details()

        if session:  # Not being triggered by Chrome or FireTablet Plex App
            self._session = session
        if device:
            self._device = device
            if "127.0.0.1" in self._device.url("/"):
                self._device.proxyThroughServer()
            self._session = None
            self._machine_identifier = self._device.machineIdentifier
            self._name = self._device.title or DEVICE_DEFAULT_NAME
            self._device_protocol_capabilities = (
                self._device.protocolCapabilities)

            # set valid session, preferring device session
            if self.plex_sessions.get(self._device.machineIdentifier, None):
                self._session = self.plex_sessions.get(
                    self._device.machineIdentifier, None)

        if self._session:
            if self._device.machineIdentifier is not None and \
                    self._session.players:
                self._is_player_available = True
                self._player = [p for p in self._session.players
                                if p.machineIdentifier ==
                                self._device.machineIdentifier][0]
                self._name = self._player.title
                self._player_state = self._player.state
                self._session_username = self._session.usernames[0]
                self._make = self._player.device
            else:
                self._is_player_available = False
            self._media_position = self._session.viewOffset
            self._media_content_id = self._session.ratingKey
            self._media_content_rating = getattr(
                self._session, 'contentRating', None)

        self._set_player_state()

        if self._is_player_active and self._session is not None:
            self._session_type = self._session.type
            self._media_duration = self._session.duration
            #  title (movie name, tv episode name, music song name)
            self._media_title = self._session.title
            # media type
            self._set_media_type()
            self._app_name = self._session.section().title \
                if self._session.section() is not None else ''
            self._set_media_image()
        else:
            self._session_type = None

    def _set_media_image(self):
        thumb_url = self._session.thumbUrl
        if (self.media_content_type is MEDIA_TYPE_TVSHOW
                and not self.config.get(CONF_USE_EPISODE_ART)):
            thumb_url = self._session.url(self._session.grandparentThumb)

        if thumb_url is None:
            _LOGGER.debug("Using media art because media thumb "
                          "was not found: %s", self.entity_id)
            thumb_url = self.session.url(self._session.art)

        self._media_image_url = thumb_url

    def set_availability(self, available):
        """Set the device as available/unavailable noting time."""
        if not available:
            self._clear_media_details()
            if self._marked_unavailable is None:
                self._marked_unavailable = dt_util.utcnow()
        else:
            self._marked_unavailable = None

        self._available = available

    def _set_player_state(self):
        if self._player_state == 'playing':
            self._is_player_active = True
            self._state = STATE_PLAYING
        elif self._player_state == 'paused':
            self._is_player_active = True
            self._state = STATE_PAUSED
        elif self.device:
            self._is_player_active = False
            self._state = STATE_IDLE
        else:
            self._is_player_active = False
            self._state = STATE_OFF

    def _set_media_type(self):
        if self._session_type in ['clip', 'episode']:
            self._media_content_type = MEDIA_TYPE_TVSHOW

            # season number (00)
            if callable(self._session.season):
                self._media_season = str(
                    (self._session.season()).index).zfill(2)
            elif self._session.parentIndex is not None:
                self._media_season = self._session.parentIndex.zfill(2)
            else:
                self._media_season = None
            # show name
            self._media_series_title = self._session.grandparentTitle
            # episode number (00)
            if self._session.index is not None:
                self._media_episode = str(self._session.index).zfill(2)

        elif self._session_type == 'movie':
            self._media_content_type = MEDIA_TYPE_MOVIE
            if self._session.year is not None and \
                    self._media_title is not None:
                self._media_title += ' (' + str(self._session.year) + ')'

        elif self._session_type == 'track':
            self._media_content_type = MEDIA_TYPE_MUSIC
            self._media_album_name = self._session.parentTitle
            self._media_album_artist = self._session.grandparentTitle
            self._media_track = self._session.index
            self._media_artist = self._session.originalTitle
            # use album artist if track artist is missing
            if self._media_artist is None:
                _LOGGER.debug("Using album artist because track artist "
                              "was not found: %s", self.entity_id)
                self._media_artist = self._media_album_artist

    def force_idle(self):
        """Force client to idle."""
        self._state = STATE_IDLE
        self._session = None
        self._clear_media_details()

    @property
    def unique_id(self):
        """Return the id of this plex client."""
        return self.machine_identifier

    @property
    def available(self):
        """Return the availability of the client."""
        return self._available

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def machine_identifier(self):
        """Return the machine identifier of the device."""
        return self._machine_identifier

    @property
    def app_name(self):
        """Return the library name of playing media."""
        return self._app_name

    @property
    def device(self):
        """Return the device, if any."""
        return self._device

    @property
    def marked_unavailable(self):
        """Return time device was marked unavailable."""
        return self._marked_unavailable

    @property
    def session(self):
        """Return the session, if any."""
        return self._session

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the latest details."""
        self.update_devices(no_throttle=True)
        self.update_sessions(no_throttle=True)

    @property
    def _active_media_plexapi_type(self):
        """Get the active media type required by PlexAPI commands."""
        if self.media_content_type is MEDIA_TYPE_MUSIC:
            return 'music'

        return 'video'

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self._media_content_id

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        if self._session_type == 'clip':
            _LOGGER.debug("Clip content type detected, "
                          "compatibility may vary: %s", self.entity_id)
            return MEDIA_TYPE_TVSHOW
        if self._session_type == 'episode':
            return MEDIA_TYPE_TVSHOW
        if self._session_type == 'movie':
            return MEDIA_TYPE_MOVIE
        if self._session_type == 'track':
            return MEDIA_TYPE_MUSIC

        return None

    @property
    def media_artist(self):
        """Return the artist of current playing media, music track only."""
        return self._media_artist

    @property
    def media_album_name(self):
        """Return the album name of current playing media, music track only."""
        return self._media_album_name

    @property
    def media_album_artist(self):
        """Return the album artist of current playing media, music only."""
        return self._media_album_artist

    @property
    def media_track(self):
        """Return the track number of current playing media, music only."""
        return self._media_track

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return self._media_duration

    @property
    def media_image_url(self):
        """Return the image URL of current playing media."""
        return self._media_image_url

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return self._media_title

    @property
    def media_season(self):
        """Return the season of current playing media (TV Show only)."""
        return self._media_season

    @property
    def media_series_title(self):
        """Return the title of the series of current playing media."""
        return self._media_series_title

    @property
    def media_episode(self):
        """Return the episode of current playing media (TV Show only)."""
        return self._media_episode

    @property
    def make(self):
        """Return the make of the device (ex. SHIELD Android TV)."""
        return self._make

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if not self._is_player_active:
            return None

        # force show all controls
        if self.config.get(CONF_SHOW_ALL_CONTROLS):
            return (SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK |
                    SUPPORT_NEXT_TRACK | SUPPORT_STOP |
                    SUPPORT_VOLUME_SET | SUPPORT_PLAY |
                    SUPPORT_TURN_OFF | SUPPORT_VOLUME_MUTE)

        # only show controls when we know what device is connecting
        if not self._make:
            return None
        # no mute support
        if self.make.lower() == "shield android tv":
            _LOGGER.debug(
                "Shield Android TV client detected, disabling mute "
                "controls: %s", self.entity_id)
            return (SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK |
                    SUPPORT_NEXT_TRACK | SUPPORT_STOP |
                    SUPPORT_VOLUME_SET | SUPPORT_PLAY |
                    SUPPORT_TURN_OFF)
        # Only supports play,pause,stop (and off which really is stop)
        if self.make.lower().startswith("tivo"):
            _LOGGER.debug(
                "Tivo client detected, only enabling pause, play, "
                "stop, and off controls: %s", self.entity_id)
            return (SUPPORT_PAUSE | SUPPORT_PLAY | SUPPORT_STOP |
                    SUPPORT_TURN_OFF)
        # Not all devices support playback functionality
        # Playback includes volume, stop/play/pause, etc.
        if self.device and 'playback' in self._device_protocol_capabilities:
            return (SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK |
                    SUPPORT_NEXT_TRACK | SUPPORT_STOP |
                    SUPPORT_VOLUME_SET | SUPPORT_PLAY |
                    SUPPORT_TURN_OFF | SUPPORT_VOLUME_MUTE)

        return None

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        if self.device and 'playback' in self._device_protocol_capabilities:
            self.device.setVolume(
                int(volume * 100), self._active_media_plexapi_type)
            self._volume_level = volume  # store since we can't retrieve

    @property
    def volume_level(self):
        """Return the volume level of the client (0..1)."""
        if (self._is_player_active and self.device and
                'playback' in self._device_protocol_capabilities):
            return self._volume_level

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        if self._is_player_active and self.device:
            return self._volume_muted

    def mute_volume(self, mute):
        """Mute the volume.

        Since we can't actually mute, we'll:
        - On mute, store volume and set volume to 0
        - On unmute, set volume to previously stored volume
        """
        if not (self.device and
                'playback' in self._device_protocol_capabilities):
            return

        self._volume_muted = mute
        if mute:
            self._previous_volume_level = self._volume_level
            self.set_volume_level(0)
        else:
            self.set_volume_level(self._previous_volume_level)

    def media_play(self):
        """Send play command."""
        if self.device and 'playback' in self._device_protocol_capabilities:
            self.device.play(self._active_media_plexapi_type)

    def media_pause(self):
        """Send pause command."""
        if self.device and 'playback' in self._device_protocol_capabilities:
            self.device.pause(self._active_media_plexapi_type)

    def media_stop(self):
        """Send stop command."""
        if self.device and 'playback' in self._device_protocol_capabilities:
            self.device.stop(self._active_media_plexapi_type)

    def turn_off(self):
        """Turn the client off."""
        # Fake it since we can't turn the client off
        self.media_stop()

    def media_next_track(self):
        """Send next track command."""
        if self.device and 'playback' in self._device_protocol_capabilities:
            self.device.skipNext(self._active_media_plexapi_type)

    def media_previous_track(self):
        """Send previous track command."""
        if self.device and 'playback' in self._device_protocol_capabilities:
            self.device.skipPrevious(self._active_media_plexapi_type)

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        if not (self.device and
                'playback' in self._device_protocol_capabilities):
            return

        src = json.loads(media_id)

        media = None
        if media_type == 'MUSIC':
            media = self.device.server.library.section(
                src['library_name']).get(src['artist_name']).album(
                    src['album_name']).get(src['track_name'])
        elif media_type == 'EPISODE':
            media = self._get_tv_media(
                src['library_name'], src['show_name'],
                src['season_number'], src['episode_number'])
        elif media_type == 'PLAYLIST':
            media = self.device.server.playlist(src['playlist_name'])
        elif media_type == 'VIDEO':
            media = self.device.server.library.section(
                src['library_name']).get(src['video_name'])

        import plexapi.playlist
        if (media and media_type == 'EPISODE' and
                isinstance(media, plexapi.playlist.Playlist)):
            # delete episode playlist after being loaded into a play queue
            self._client_play_media(media=media, delete=True,
                                    shuffle=src['shuffle'])
        elif media:
            self._client_play_media(media=media, shuffle=src['shuffle'])

    def _get_tv_media(self, library_name, show_name, season_number,
                      episode_number):
        """Find TV media and return a Plex media object."""
        target_season = None
        target_episode = None

        show = self.device.server.library.section(library_name).get(
            show_name)

        if not season_number:
            playlist_name = "{} - {} Episodes".format(
                self.entity_id, show_name)
            return self.device.server.createPlaylist(
                playlist_name, show.episodes())

        for season in show.seasons():
            if int(season.seasonNumber) == int(season_number):
                target_season = season
                break

        if target_season is None:
            _LOGGER.error("Season not found: %s\\%s - S%sE%s", library_name,
                          show_name,
                          str(season_number).zfill(2),
                          str(episode_number).zfill(2))
        else:
            if not episode_number:
                playlist_name = "{} - {} Season {} Episodes".format(
                    self.entity_id, show_name, str(season_number))
                return self.device.server.createPlaylist(
                    playlist_name, target_season.episodes())

            for episode in target_season.episodes():
                if int(episode.index) == int(episode_number):
                    target_episode = episode
                    break

            if target_episode is None:
                _LOGGER.error("Episode not found: %s\\%s - S%sE%s",
                              library_name, show_name,
                              str(season_number).zfill(2),
                              str(episode_number).zfill(2))

        return target_episode

    def _client_play_media(self, media, delete=False, **params):
        """Instruct Plex client to play a piece of media."""
        if not (self.device and
                'playback' in self._device_protocol_capabilities):
            _LOGGER.error("Client cannot play media: %s", self.entity_id)
            return

        import plexapi.playqueue
        playqueue = plexapi.playqueue.PlayQueue.create(
            self.device.server, media, **params)

        # Delete dynamic playlists used to build playqueue (ex. play tv season)
        if delete:
            media.delete()

        server_url = self.device.server.baseurl.split(':')
        self.device.sendCommand('playback/playMedia', **dict({
            'machineIdentifier': self.device.server.machineIdentifier,
            'address': server_url[1].strip('/'),
            'port': server_url[-1],
            'key': media.key,
            'containerKey':
                '/playQueues/{}?window=100&own=1'.format(
                    playqueue.playQueueID),
        }, **params))

    @property
    def device_state_attributes(self):
        """Return the scene state attributes."""
        attr = {
            'media_content_rating': self._media_content_rating,
            'session_username': self._session_username,
            'media_library_name': self._app_name
        }

        return attr
