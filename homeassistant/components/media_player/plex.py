"""
Support to interface with the Plex API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.plex/
"""
import json
import logging
import os
from datetime import timedelta
from urllib.parse import urlparse

import requests
import voluptuous as vol

from homeassistant import util
from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, MEDIA_TYPE_TVSHOW, MEDIA_TYPE_VIDEO, PLATFORM_SCHEMA,
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    MediaPlayerDevice)
from homeassistant.const import (
    DEVICE_DEFAULT_NAME, STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import track_utc_time_change

REQUIREMENTS = ['plexapi==2.0.2']

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)

PLEX_CONFIG_FILE = 'plex.conf'

CONF_INCLUDE_NON_CLIENTS = 'include_non_clients'
CONF_USE_EPISODE_ART = 'use_episode_art'
CONF_USE_CUSTOM_ENTITY_IDS = 'use_custom_entity_ids'
CONF_SHOW_ALL_CONTROLS = 'show_all_controls'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_INCLUDE_NON_CLIENTS, default=False):
    cv.boolean,
    vol.Optional(CONF_USE_EPISODE_ART, default=False):
    cv.boolean,
    vol.Optional(CONF_USE_CUSTOM_ENTITY_IDS, default=False):
    cv.boolean,
})


def config_from_file(filename, config=None):
    """Small configuration file management function."""
    if config:
        # We're writing configuration
        try:
            with open(filename, 'w') as fdesc:
                fdesc.write(json.dumps(config))
        except IOError as error:
            _LOGGER.error("Saving config file failed: %s", error)
            return False
        return True
    else:
        # We're reading config
        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as fdesc:
                    return json.loads(fdesc.read())
            except IOError as error:
                _LOGGER.error("Reading config file failed: %s", error)
                # This won't work yet
                return False
        else:
            return {}


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up the Plex platform."""
    # get config from plex.conf
    file_config = config_from_file(hass.config.path(PLEX_CONFIG_FILE))

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
        hass, config, add_devices_callback
    )


def setup_plexserver(
        host, token, has_ssl, verify_ssl, hass, config, add_devices_callback):
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
        request_configuration(host, hass, config, add_devices_callback)
        return

    # If we came here and configuring this host, mark as done
    if host in _CONFIGURING:
        request_id = _CONFIGURING.pop(host)
        configurator = hass.components.configurator
        configurator.request_done(request_id)
        _LOGGER.info("Discovery configuration done")

    # Save config
    if not config_from_file(
            hass.config.path(PLEX_CONFIG_FILE), {host: {
                'token': token,
                'ssl': has_ssl,
                'verify': verify_ssl,
            }}):
        _LOGGER.error("Failed to save configuration file")

    _LOGGER.info('Connected to: %s://%s', http_prefix, host)

    plex_clients = {}
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
            _LOGGER.error("Could not connect to plex server at http://%s (%s)",
                          host, ex)
            return

        new_plex_clients = []
        for device in devices:
            # For now, let's allow all deviceClass types
            if device.deviceClass in ['badClient']:
                continue

            if device.machineIdentifier not in plex_clients:
                new_client = PlexClient(config, device, None,
                                        plex_sessions, update_devices,
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
                    new_client = PlexClient(config, None, session,
                                            plex_sessions, update_devices,
                                            update_sessions)
                    plex_clients[machine_identifier] = new_client
                    new_plex_clients.append(new_client)
                else:
                    plex_clients[machine_identifier].refresh(None, session)

        for machine_identifier, client in plex_clients.items():
            # force devices to idle that do not have a valid session
            if client.session is None:
                client.force_idle()

        if new_plex_clients:
            add_devices_callback(new_plex_clients)

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_sessions():
        """Update the sessions objects."""
        try:
            sessions = plexserver.sessions()
        except plexapi.exceptions.BadRequest:
            _LOGGER.exception("Error listing plex sessions")
            return
        except requests.exceptions.RequestException as ex:
            _LOGGER.error("Could not connect to plex server at http://%s (%s)",
                          host, ex)
            return

        plex_sessions.clear()
        for session in sessions:
            if (session.player is not None and
                    session.player.machineIdentifier is not None):
                plex_sessions[session.player.machineIdentifier] = session

    update_sessions()
    update_devices()


def request_configuration(host, hass, config, add_devices_callback):
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
            hass, config, add_devices_callback
        )

    _CONFIGURING[host] = configurator.request_config(
        'Plex Media Server',
        plex_configuration_callback,
        description=('Enter the X-Plex-Token'),
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
        from plexapi.utils import NA
        self._app_name = ''
        self._device = None
        self._device_protocol_capabilities = None
        self._is_player_active = False
        self._is_player_available = False
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
        self.na_type = NA
        self.config = config
        self.plex_sessions = plex_sessions
        self.update_devices = update_devices
        self.update_sessions = update_sessions

        self._clear_media()

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

    def _clear_media(self):
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

    def refresh(self, device, session):
        """Refresh key device data."""
        # new data refresh
        self._clear_media()

        if session:  # Not being triggered by Chrome or FireTablet Plex App
            self._session = session
        if device:
            self._device = device
            self._session = None

        if self._device:
            self._machine_identifier = self._convert_na_to_none(
                self._device.machineIdentifier)
            self._name = self._convert_na_to_none(
                self._device.title) or DEVICE_DEFAULT_NAME
            self._device_protocol_capabilities = (
                self._device.protocolCapabilities)

        # set valid session, preferring device session
        if self._device and self.plex_sessions.get(
                self._device.machineIdentifier, None):
            self._session = self._convert_na_to_none(self.plex_sessions.get(
                self._device.machineIdentifier, None))

        if self._session:
            self._media_position = self._convert_na_to_none(
                self._session.viewOffset)
            self._media_content_id = self._convert_na_to_none(
                self._session.ratingKey)
            self._media_content_rating = self._convert_na_to_none(
                self._session.contentRating)

        # player dependent data
        if self._session and self._session.player:
            self._is_player_available = True
            self._machine_identifier = self._convert_na_to_none(
                self._session.player.machineIdentifier)
            self._name = self._convert_na_to_none(self._session.player.title)
            self._player_state = self._session.player.state
            self._session_username = self._convert_na_to_none(
                self._session.username)
            self._make = self._convert_na_to_none(self._session.player.device)
        else:
            self._is_player_available = False

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

        if self._is_player_active and self._session is not None:
            self._session_type = self._session.type
            self._media_duration = self._convert_na_to_none(
                self._session.duration)
        else:
            self._session_type = None

        # media type
        if self._session_type == 'clip':
            _LOGGER.debug("Clip content type detected, compatibility may "
                          "vary: %s", self.entity_id)
            self._media_content_type = MEDIA_TYPE_TVSHOW
        elif self._session_type == 'episode':
            self._media_content_type = MEDIA_TYPE_TVSHOW
        elif self._session_type == 'movie':
            self._media_content_type = MEDIA_TYPE_VIDEO
        elif self._session_type == 'track':
            self._media_content_type = MEDIA_TYPE_MUSIC

        # title (movie name, tv episode name, music song name)
        if self._session and self._is_player_active:
            self._media_title = self._convert_na_to_none(self._session.title)

        # Movies
        if (self.media_content_type == MEDIA_TYPE_VIDEO and
                self._convert_na_to_none(self._session.year) is not None):
            self._media_title += ' (' + str(self._session.year) + ')'

        # TV Show
        if self._media_content_type is MEDIA_TYPE_TVSHOW:
            # season number (00)
            if callable(self._convert_na_to_none(self._session.seasons)):
                self._media_season = self._convert_na_to_none(
                    self._session.seasons()[0].index).zfill(2)
            elif self._convert_na_to_none(
                    self._session.parentIndex) is not None:
                self._media_season = self._session.parentIndex.zfill(2)
            else:
                self._media_season = None
            # show name
            self._media_series_title = self._convert_na_to_none(
                self._session.grandparentTitle)
            # episode number (00)
            if self._convert_na_to_none(self._session.index) is not None:
                self._media_episode = str(self._session.index).zfill(2)

        # Music
        if self._media_content_type == MEDIA_TYPE_MUSIC:
            self._media_album_name = self._convert_na_to_none(
                self._session.parentTitle)
            self._media_album_artist = self._convert_na_to_none(
                self._session.grandparentTitle)
            self._media_track = self._convert_na_to_none(self._session.index)
            self._media_artist = self._convert_na_to_none(
                self._session.originalTitle)
            # use album artist if track artist is missing
            if self._media_artist is None:
                _LOGGER.debug("Using album artist because track artist "
                              "was not found: %s", self.entity_id)
                self._media_artist = self._media_album_artist

        # set app name to library name
        if (self._session is not None
                and self._session.librarySectionID is not None):
            self._app_name = self._convert_na_to_none(
                self._session.server.library.sectionByID(
                    self._session.librarySectionID).title)
        else:
            self._app_name = ''

        # media image url
        if self._session is not None:
            thumb_url = self._get_thumbnail_url(self._session.thumb)
            if (self.media_content_type is MEDIA_TYPE_TVSHOW
                    and not self.config.get(CONF_USE_EPISODE_ART)):
                thumb_url = self._get_thumbnail_url(
                    self._session.grandparentThumb)

            if thumb_url is None:
                _LOGGER.debug("Using media art because media thumb "
                              "was not found: %s", self.entity_id)
                thumb_url = self._get_thumbnail_url(self._session.art)

            self._media_image_url = thumb_url

    def _get_thumbnail_url(self, property_value):
        """Return full URL (if exists) for a thumbnail property."""
        if self._convert_na_to_none(property_value) is None:
            return None

        if self._session is None or self._session.server is None:
            return None

        url = self._session.server.url(property_value)
        response = requests.get(url, verify=False)
        if response and response.status_code == 200:
            return url

    def force_idle(self):
        """Force client to idle."""
        self._state = STATE_IDLE
        self._session = None
        self._clear_media()

    @property
    def unique_id(self):
        """Return the id of this plex client."""
        return '{}.{}'.format(self.__class__, self.machine_identifier or
                              self.name)

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

    # pylint: disable=no-self-use, singleton-comparison
    def _convert_na_to_none(self, value):
        """Convert PlexAPI _NA() instances to None."""
        # PlexAPI will return a "__NA__" object which can be compared to
        # None, but isn't actually None - this converts it to a real None
        # type so that lower layers don't think it's a URL and choke on it
        if value is self.na_type:
            return None

        return value

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
        elif self._session_type == 'episode':
            return MEDIA_TYPE_TVSHOW
        elif self._session_type == 'movie':
            return MEDIA_TYPE_VIDEO
        elif self._session_type == 'track':
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
        elif self.make.lower() == "shield android tv":
            _LOGGER.debug(
                "Shield Android TV client detected, disabling mute "
                "controls: %s", self.entity_id)
            return (SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK |
                    SUPPORT_NEXT_TRACK | SUPPORT_STOP |
                    SUPPORT_VOLUME_SET | SUPPORT_PLAY |
                    SUPPORT_TURN_OFF)
        # Only supports play,pause,stop (and off which really is stop)
        elif self.make.lower().startswith("tivo"):
            _LOGGER.debug(
                "Tivo client detected, only enabling pause, play, "
                "stop, and off controls: %s", self.entity_id)
            return (SUPPORT_PAUSE | SUPPORT_PLAY | SUPPORT_STOP |
                    SUPPORT_TURN_OFF)
        # Not all devices support playback functionality
        # Playback includes volume, stop/play/pause, etc.
        elif self.device and 'playback' in self._device_protocol_capabilities:
            return (SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK |
                    SUPPORT_NEXT_TRACK | SUPPORT_STOP |
                    SUPPORT_VOLUME_SET | SUPPORT_PLAY |
                    SUPPORT_TURN_OFF | SUPPORT_VOLUME_MUTE)

        return None

    def _local_client_control_fix(self):
        """Detect if local client and adjust url to allow control."""
        if self.device is None:
            return

        # if this device's machineIdentifier matches an active client
        # with a loopback address, the device must be local or casting
        for client in self.device.server.clients():
            if ("127.0.0.1" in client.baseurl and
                    client.machineIdentifier == self.device.machineIdentifier):
                # point controls to server since that's where the
                # playback is occurring
                _LOGGER.debug(
                    "Local client detected, redirecting controls to "
                    "Plex server: %s", self.entity_id)
                server_url = self.device.server.baseurl
                client_url = self.device.baseurl
                self.device.baseurl = "{}://{}:{}".format(
                    urlparse(client_url).scheme,
                    urlparse(server_url).hostname,
                    str(urlparse(client_url).port))

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        if self.device and 'playback' in self._device_protocol_capabilities:
            self._local_client_control_fix()
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
            self._local_client_control_fix()
            self.device.play(self._active_media_plexapi_type)

    def media_pause(self):
        """Send pause command."""
        if self.device and 'playback' in self._device_protocol_capabilities:
            self._local_client_control_fix()
            self.device.pause(self._active_media_plexapi_type)

    def media_stop(self):
        """Send stop command."""
        if self.device and 'playback' in self._device_protocol_capabilities:
            self._local_client_control_fix()
            self.device.stop(self._active_media_plexapi_type)

    def turn_off(self):
        """Turn the client off."""
        # Fake it since we can't turn the client off
        self.media_stop()

    def media_next_track(self):
        """Send next track command."""
        if self.device and 'playback' in self._device_protocol_capabilities:
            self._local_client_control_fix()
            self.device.skipNext(self._active_media_plexapi_type)

    def media_previous_track(self):
        """Send previous track command."""
        if self.device and 'playback' in self._device_protocol_capabilities:
            self._local_client_control_fix()
            self.device.skipPrevious(self._active_media_plexapi_type)

    # pylint: disable=W0613
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

        self._local_client_control_fix()

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
        attr = {}
        attr['media_content_rating'] = self._media_content_rating
        attr['session_username'] = self._session_username
        attr['media_library_name'] = self._app_name

        return attr
