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
import voluptuous as vol
import homeassistant.util as util
import homeassistant.helpers.config_validation as cv
import asyncio

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from homeassistant.components.media_player import (
    MEDIA_TYPE_TVSHOW, MEDIA_TYPE_VIDEO, MEDIA_TYPE_MUSIC, SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_PAUSE, SUPPORT_STOP, SUPPORT_VOLUME_SET,
    SUPPORT_PLAY, SUPPORT_VOLUME_MUTE, SUPPORT_TURN_OFF, SUPPORT_SEEK,
    PLATFORM_SCHEMA, MediaPlayerDevice)
from homeassistant.const import (DEVICE_DEFAULT_NAME, STATE_IDLE, STATE_OFF,
                                 STATE_PAUSED, STATE_PLAYING)
from homeassistant.loader import get_component
from homeassistant.helpers.event import (track_utc_time_change)

REQUIREMENTS = ['plexapi==2.0.2']
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)

PLEX_CONFIG_FILE = 'plex.conf'

GROUP_ACTIVE_DEVICES = 'group._plex_devices_active'
GROUP_INACTIVE_DEVICES = 'group._plex_devices_inactive'

# includes non-controllable clients (ex. PlexConnect Apple TV's)
CONF_INCLUDE_NON_CLIENTS = 'include_non_clients'
# Use episode art instead of show art
CONF_USE_EPISODE_ART = 'use_episode_art'
# Automatically group devices into active and inactive groups
CONF_USE_DYNAMIC_GROUPS = 'use_dynamic_groups'
# Name entities by device id (less ambiguous, more predictable names)
CONF_USE_CUSTOM_ENTITY_IDS = 'use_custom_entity_ids'
# Show all controls instead of only displaying ones within client capabilities
CONF_SHOW_ALL_CONTROLS = 'show_all_controls'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_INCLUDE_NON_CLIENTS, default=False):
    cv.boolean,
    vol.Optional(CONF_USE_EPISODE_ART, default=False):
    cv.boolean,
    vol.Optional(CONF_USE_DYNAMIC_GROUPS, default=False):
    cv.boolean,
    vol.Optional(CONF_USE_CUSTOM_ENTITY_IDS, default=False):
    cv.boolean,
})

# Map ip to request id for configuring
_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

SUPPORT_PLEX = SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_STOP | SUPPORT_VOLUME_SET | SUPPORT_PLAY | SUPPORT_SEEK | \
    SUPPORT_TURN_OFF

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def config_from_file(filename, config=None):
    """Small configuration file management function."""
    if config:
        # We're writing configuration
        try:
            with open(filename, 'w') as fdesc:
                fdesc.write(json.dumps(config))
        except IOError as error:
            _LOGGER.error('Saving config file failed: %s', error)
            return False
        return True
    else:
        # We're reading config
        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as fdesc:
                    return json.loads(fdesc.read())
            except IOError as error:
                _LOGGER.error('Reading config file failed: %s', error)
                # This won't work yet
                return False
        else:
            return {}


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the Plex platform."""
    # optional parameters
    optional_config = {}
    optional_config["entity_namespace"] = config.get("entity_namespace")
    optional_config[CONF_INCLUDE_NON_CLIENTS] = config.get(
        CONF_INCLUDE_NON_CLIENTS)
    optional_config[CONF_USE_EPISODE_ART] = config.get(CONF_USE_EPISODE_ART)
    optional_config[CONF_USE_DYNAMIC_GROUPS] = config.get(
        CONF_USE_DYNAMIC_GROUPS)
    optional_config[CONF_USE_CUSTOM_ENTITY_IDS] = config.get(
        CONF_USE_CUSTOM_ENTITY_IDS)
    optional_config[CONF_SHOW_ALL_CONTROLS] = config.get(
        CONF_SHOW_ALL_CONTROLS)

    config = config_from_file(hass.config.path(PLEX_CONFIG_FILE))
    if len(config):
        # Setup a configured PlexServer
        host, token = config.popitem()
        token = token['token']
    # Via discovery
    elif discovery_info is not None:
        # Parse discovery data
        host = urlparse(discovery_info[1]).netloc
        _LOGGER.info('Discovered PLEX server: %s', host)

        if host in _CONFIGURING:
            return
        token = None
    else:
        return

    setup_plexserver(host, token, hass, optional_config, add_devices_callback)


def set_group_members(hass, group_entity_id, member_entity_id_list):
    """Creates group if doesn't exist and sets memberships"""
    hass.states.set(group_entity_id, 'off',
                    {'entity_id': member_entity_id_list})


def setup_plexserver(host, token, hass, optional_config, add_devices_callback):
    """Setup a plexserver based on host parameter."""
    import plexapi.server
    import plexapi.exceptions

    try:
        plexserver = plexapi.server.PlexServer('http://%s' % host, token)
    except (plexapi.exceptions.BadRequest, plexapi.exceptions.Unauthorized,
            plexapi.exceptions.NotFound) as error:
        _LOGGER.info(error)
        # No token or wrong token
        request_configuration(host, hass, optional_config,
                              add_devices_callback)
        return

    # If we came here and configuring this host, mark as done
    if host in _CONFIGURING:
        request_id = _CONFIGURING.pop(host)
        configurator = get_component('configurator')
        configurator.request_done(request_id)
        _LOGGER.info('Discovery configuration done!')

    # Save config
    if not config_from_file(
            hass.config.path(PLEX_CONFIG_FILE), {host: {
                'token': token
            }}):
        _LOGGER.error('failed to save config file')

    _LOGGER.info('Connected to: http://%s', host)

    plex_clients = {}
    plex_sessions = {}
    track_utc_time_change(hass, lambda now: update_devices(), second=30)

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_devices():
        """Update the devices objects."""
        try:
            devices = plexserver.clients()
        except plexapi.exceptions.BadRequest:
            _LOGGER.exception('Error listing plex devices')
            return
        except OSError:
            _LOGGER.error('Could not connect to plex server at http://%s',
                          host)
            return

        new_plex_clients = []
        for device in devices:
            # For now, let's allow all deviceClass types
            if device.deviceClass in ['badClient']:
                continue

            if device.machineIdentifier not in plex_clients:
                new_client = PlexClient(optional_config, device, None,
                                        plex_sessions, update_devices,
                                        update_sessions)
                plex_clients[device.machineIdentifier] = new_client
                new_plex_clients.append(new_client)
            else:
                plex_clients[device.machineIdentifier].set_device(device)

        # add devices with a session and no client (ex. PlexConnect Apple TV's)
        if optional_config[CONF_INCLUDE_NON_CLIENTS]:
            for machine_identifier, session in plex_sessions.items():
                if machine_identifier not in plex_clients:
                    new_client = PlexClient(optional_config, None, session,
                                            plex_sessions, update_devices,
                                            update_sessions)
                    plex_clients[machine_identifier] = new_client
                    new_plex_clients.append(new_client)
                else:
                    plex_clients[machine_identifier].set_session(session)

        # force devices to idle that do not have a valid session
        for machine_identifier, client in plex_clients.items():
            if client.session is None:
                client.set_state(STATE_IDLE)

        # add devices to dynamic groups
        if optional_config[CONF_USE_DYNAMIC_GROUPS]:
            active_entity_id_list = []
            inactive_entity_id_list = []

            for machine_identifier, client in plex_clients.items():
                if client.entity_id:
                    if client.state in [STATE_IDLE, STATE_OFF]:
                        inactive_entity_id_list.append(client.entity_id)
                    else:
                        active_entity_id_list.append(client.entity_id)

            # set groups with updated memberships
            set_group_members(hass, GROUP_ACTIVE_DEVICES,
                              active_entity_id_list)
            set_group_members(hass, GROUP_INACTIVE_DEVICES,
                              inactive_entity_id_list)

        if new_plex_clients:
            add_devices_callback(new_plex_clients)

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_sessions():
        """Update the sessions objects."""
        try:
            sessions = plexserver.sessions()
        except plexapi.exceptions.BadRequest:
            _LOGGER.exception('Error listing plex sessions')
            return

        plex_sessions.clear()
        for session in sessions:
            if session.player:
                plex_sessions[session.player.machineIdentifier] = session

    update_sessions()
    update_devices()


def request_configuration(host, hass, optional_config, add_devices_callback):
    """Request configuration steps from the user."""
    configurator = get_component('configurator')
    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(_CONFIGURING[host],
                                   'Failed to register, please try again.')

        return

    def plex_configuration_callback(data):
        """The actions to do when our configuration callback is called."""
        setup_plexserver(host,
                         data.get('token'), hass, optional_config,
                         add_devices_callback)

    _CONFIGURING[host] = configurator.request_config(
        hass,
        'Plex Media Server',
        plex_configuration_callback,
        description=('Enter the X-Plex-Token'),
        entity_picture='/static/images/logo_plex_mediaserver.png',
        submit_caption='Confirm',
        fields=[{
            'id': 'token',
            'name': 'X-Plex-Token',
            'type': ''
        }])


class PlexClient(MediaPlayerDevice):
    """Representation of a Plex device."""

    # pylint: disable=attribute-defined-outside-init
    def __init__(self, optional_config, device, session, plex_sessions,
                 update_devices, update_sessions):
        """Initialize the Plex device."""
        from plexapi.utils import NA

        self.na_type = NA
        self._session = None
        self.optional_config = optional_config
        self.plex_sessions = plex_sessions
        self.update_devices = update_devices
        self.update_sessions = update_sessions
        self.set_device(device)
        self.set_session(session)
        self._state = STATE_IDLE
        self._volume_muted = False  # since we can't retrieve remotely
        self._volume_level = 1  # since we can't retrieve remotely
        self._previous_volume_level = 1  # Used in fake muting
        self._media_position_updated_at = None

        if self.optional_config[CONF_USE_CUSTOM_ENTITY_IDS]:
            prefix = ''
            # allow for namespace prefixing when using custom entity names
            if optional_config["entity_namespace"]:
                prefix = optional_config["entity_namespace"] + '_'

            # rename the entity
            if self.machine_identifier:
                self.entity_id = "%s.%s%s" % (
                    'media_player', prefix,
                    self.machine_identifier.lower().replace('-', '_'))
            else:
                if self.name:
                    self.entity_id = "%s.%s%s" % (
                        'media_player', prefix,
                        self.name.lower().replace('-', '_'))

    def set_device(self, device):
        """Set the device property."""
        self.device = device

    def set_session(self, session):
        """Set the session property."""
        self._session = session

    def set_state(self, state):
        """Set the state property."""
        self._state = state

    @property
    def unique_id(self):
        """Return the id of this plex client."""
        return '{}.{}'.format(self.__class__, self.machine_identifier or
                              self.name)

    @property
    def name(self):
        """Return the name of the device."""
        if self.device:
            return self._convert_na_to_none(
                self.device.title) or DEVICE_DEFAULT_NAME
        if self.session and self.session.player:
            return self._convert_na_to_none(self.session.player.title)

    @property
    def machine_identifier(self):
        """Return the machine identifier of the device."""
        device_id = None
        player_id = None

        if self.device:
            device_id = self._convert_na_to_none(self.device.machineIdentifier)

        if self.session and self.session.player:
            player_id = self._convert_na_to_none(
                self.session.player.machineIdentifier)

        return device_id or player_id

    @property
    def app_name(self):
        """Library name of playing media"""
        if self.session:
            if self.session.librarySectionID:
                return self._convert_na_to_none(
                    self.session.server.library.sectionByID(
                        self.session.librarySectionID).title)

    @property
    def session(self):
        """Return the session, if any."""
        if self.device:
            self._session = self.plex_sessions.get(
                self.device.machineIdentifier, None)

        return self._convert_na_to_none(self._session)

    @property
    def state(self):
        """Return the state of the device."""
        if self.session and self.session.player:
            state = self.session.player.state
            if state == 'playing':
                self._state = STATE_PLAYING
            elif state == 'paused':
                self._state = STATE_PAUSED
        # This is nasty. Need to find a way to determine alive
        elif self.device:
            self._state = STATE_IDLE
        else:
            self._state = STATE_OFF

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
        else:
            return value

    @property
    def _active_media_plexapi_type(self):
        """Get the active media type required by PlexAPI commands."""
        if self.media_content_type is MEDIA_TYPE_MUSIC:
            return 'music'
        else:
            return 'video'

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        if self.session:
            return self._convert_na_to_none(self.session.ratingKey)

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self.session:
            media_type = self.session.type
            if media_type in ('episode', 'clip'):
                return MEDIA_TYPE_TVSHOW
            elif media_type == 'movie':
                return MEDIA_TYPE_VIDEO
            elif media_type == 'track':
                return MEDIA_TYPE_MUSIC
        return None

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        if self.media_content_type is MEDIA_TYPE_MUSIC:
            if self.session:
                # use album artist if track artist is missing
                if self._convert_na_to_none(
                        self.session.originalTitle) is not None:
                    return self._convert_na_to_none(self.session.originalTitle)
                else:
                    _LOGGER.debug('Using album artist because track artist '
                                  'was not found: content id %s',
                                  self.unique_id)
                    return self._convert_na_to_none(
                        self.session.grandparentTitle)

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        if self.media_content_type is MEDIA_TYPE_MUSIC:
            if self.session:
                return self._convert_na_to_none(self.session.parentTitle)

    @property
    def media_album_artist(self):
        """Album artist of current playing media, music track only."""
        if self.media_content_type is MEDIA_TYPE_MUSIC:
            if self.session:
                return self._convert_na_to_none(self.session.grandparentTitle)

    @property
    def media_track(self):
        """Track number of current playing media, music track only."""
        if self.media_content_type is MEDIA_TYPE_MUSIC:
            if self.session:
                return self._convert_na_to_none(self.session.index)

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self.session:
            return self._convert_na_to_none(self.session.duration)

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self.session:
            return self._convert_na_to_none(self.session.viewOffset)

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        if self.state == STATE_PLAYING:
            self._media_position_updated_at = util.dt.utcnow()
        return self._media_position_updated_at

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self.session:
            thumb_url = self._convert_na_to_none(self.session.thumb)
            if self.media_content_type is MEDIA_TYPE_TVSHOW:
                if not self.optional_config[CONF_USE_EPISODE_ART]:
                    thumb_url = self._convert_na_to_none(
                        self.session.grandparentThumb)

            if thumb_url:
                thumb_url = self.session.server.url(thumb_url)
                thumb_response = requests.get(thumb_url, verify=False)
                if thumb_response.status_code != 200:
                    _LOGGER.debug('Using art because thumbnail was missing: '
                                  'content id %s', self.media_content_id)
                    thumb_url = self.session.server.url(
                        self._convert_na_to_none(self.session.art))
            else:
                _LOGGER.debug('Using art because thumbnail was not found: '
                              'content id %s', self.media_content_id)
                thumb_url = self.session.server.url(
                    self._convert_na_to_none(self.session.art))

            return thumb_url

    @property
    def media_title(self):
        """Title of current playing media."""
        # find a string we can use as a title
        title = None
        if self.session:
            if self._convert_na_to_none(self.session.title) is not None:
                title = self.session.title

                # append year for movies
                if self.media_content_type is MEDIA_TYPE_VIDEO:
                    if self._convert_na_to_none(self.session.year) is not None:
                        title = title + " (" + str(self.session.year) + ")"

        return title

    @property
    def media_season(self):
        """Season of curent playing media (TV Show only)."""
        if self.media_content_type is MEDIA_TYPE_TVSHOW:
            if self.session is not None:
                if callable(self.session):
                    return self._convert_na_to_none(
                        self.session.seasons()[0].index).zfill(2)
                elif self._convert_na_to_none(
                        self.session.parentIndex) is not None:
                    return self.session.parentIndex.zfill(2)

        return None

    @property
    def media_series_title(self):
        """The title of the series of current playing media (TV Show only)."""
        if self.media_content_type is MEDIA_TYPE_TVSHOW:
            if self.session:
                return self._convert_na_to_none(self.session.grandparentTitle)

    @property
    def media_episode(self):
        """Episode of current playing media (TV Show only)."""
        if self.media_content_type is MEDIA_TYPE_TVSHOW:
            if self.session:
                if self._convert_na_to_none(self.session.index) is not None:
                    return str(self.session.index).zfill(2)

    @property
    def make(self):
        """The make of the device (ex. SHIELD Android TV)."""
        if self.session and self.session.player:
            return self._convert_na_to_none(self.session.player.device)

    @property
    def supported_features(self):
        """Flag media player features that are supported."""

        # force show all controls
        if self.optional_config[CONF_SHOW_ALL_CONTROLS]:
            return SUPPORT_PLEX | SUPPORT_VOLUME_MUTE
        else:
            if self.make == "SHIELD Android TV":
                return SUPPORT_PLEX
            elif self.device:
                return SUPPORT_PLEX | SUPPORT_VOLUME_MUTE
            else:
                return None

    def local_client_control_fix(self):
        """Detects if local client and adjusts url to allow control"""
        if self.device:
            # if this device's machineIdentifier matches an active client
            # with a loopback address, the device must be local or casting
            for client in self.device.server.clients():
                if "127.0.0.1" in client.baseurl:
                    if client.machineIdentifier == self.device.machineIdentifier:
                        # point controls to server since that's where the
                        # playback is occuring
                        server_url = self.device.server.baseurl
                        client_url = self.device.baseurl
                        self.device.baseurl = "{}://{}:{}".format(
                            urlparse(client_url).scheme,
                            urlparse(server_url).hostname,
                            str(urlparse(client_url).port))

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        if self.device:
            self.local_client_control_fix()
            self.device.setVolume(
                int(volume * 100), self._active_media_plexapi_type)
            self._volume_level = volume  # store since we can't retrieve

    @property
    def volume_level(self):
        """Return the volume level of the client (0..1)."""
        if self.device:
            return self._volume_level

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        if self.device:
            return self._volume_muted

    def mute_volume(self, mute):
        """Mute the volume.
        Since we can't actually mute, we'll:
        - On mute, store volume and set volume to 0
        - On unmute, set volume to previously stored volume
        """
        if self.device:
            self._volume_muted = mute
            if mute:
                self._previous_volume_level = self._volume_level
                self.set_volume_level(0)
            else:
                self.set_volume_level(self._previous_volume_level)

    def media_play(self):
        """Send play command."""
        if self.device:
            self.local_client_control_fix()
            self.device.play(self._active_media_plexapi_type)

    def media_pause(self):
        """Send pause command."""
        if self.device:
            self.local_client_control_fix()
            self.device.pause(self._active_media_plexapi_type)

    def media_stop(self):
        """Send stop command."""
        if self.device:
            self.local_client_control_fix()
            self.device.stop(self._active_media_plexapi_type)

    def turn_off(self):
        """Turn the client off."""
        # Fake it since we can't turn the client off
        self.media_stop()

    def media_next_track(self):
        """Send next track command."""
        if self.device:
            self.local_client_control_fix()
            self.device.skipNext(self._active_media_plexapi_type)

    def media_previous_track(self):
        """Send previous track command."""
        if self.device:
            self.local_client_control_fix()
            self.device.skipPrevious(self._active_media_plexapi_type)

    @asyncio.coroutine
    def async_play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media.
        This method must be run in the event loop and returns a coroutine.
        """
        if self.device:
            src = json.loads(media_id)

            media = None
            if media_type == 'MUSIC':
                media = self.device.server.library.section(
                    src['library_name']).get(src['artist_name']).album(
                        src['album_name']).get(src['track_name'])
            elif media_type == 'EPISODE':
                episode_number = int(src['episode_number']) + 1
                media = self.device.server.library.section(
                    src['library_name']).get(
                        src['show_name']).episodes()[episode_number]
            elif media_type == 'PLAYLIST':
                media = self.device.server.playlist(src['playlist_name'])
            elif media_type == 'VIDEO':
                media = self.device.server.library.section(
                    src['library_name']).get(src['video_name'])

            if media:
                self._client_play_media(media, shuffle=src['shuffle'])

    def _client_play_media(self, media, **params):
        """Instructs Plex client to play a piece of media."""
        if self.device:
            import plexapi.playqueue
            server_url = media.server.baseurl.split(':')
            playqueue = plexapi.playqueue.PlayQueue.create(self.device.server,
                                                           media, **params)
            self.local_client_control_fix()
            self.device.sendCommand('playback/playMedia', **dict({
                'machineIdentifier':
                self.device.server.machineIdentifier,
                'address':
                server_url[1].strip('/'),
                'port':
                server_url[-1],
                'key':
                media.key,
                'containerKey':
                '/playQueues/%s?window=100&own=1' % playqueue.playQueueID,
            }, **params))
        else:
            _LOGGER.error('Streamer cannot play media: %s', self.entity_id)
