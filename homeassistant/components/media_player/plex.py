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

import homeassistant.util as util
from homeassistant.components.media_player import (
    MEDIA_TYPE_TVSHOW, MEDIA_TYPE_VIDEO, MEDIA_TYPE_MUSIC, SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_PAUSE, SUPPORT_STOP, SUPPORT_VOLUME_SET,
    MediaPlayerDevice)
from homeassistant.const import (
    DEVICE_DEFAULT_NAME, STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING,
    STATE_UNKNOWN)
from homeassistant.loader import get_component
from homeassistant.helpers.event import (track_utc_time_change)

REQUIREMENTS = ['plexapi==2.0.2']
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)

PLEX_CONFIG_FILE = 'plex.conf'

# Map ip to request id for configuring
_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

SUPPORT_PLEX = SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_STOP | SUPPORT_VOLUME_SET


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


# pylint: disable=abstract-method
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the Plex platform."""
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

    setup_plexserver(host, token, hass, add_devices_callback)


# pylint: disable=too-many-branches
def setup_plexserver(host, token, hass, add_devices_callback):
    """Setup a plexserver based on host parameter."""
    import plexapi.server
    import plexapi.exceptions

    try:
        plexserver = plexapi.server.PlexServer('http://%s' % host, token)
    except (plexapi.exceptions.BadRequest,
            plexapi.exceptions.Unauthorized,
            plexapi.exceptions.NotFound) as error:
        _LOGGER.info(error)
        # No token or wrong token
        request_configuration(host, hass, add_devices_callback)
        return

    # If we came here and configuring this host, mark as done
    if host in _CONFIGURING:
        request_id = _CONFIGURING.pop(host)
        configurator = get_component('configurator')
        configurator.request_done(request_id)
        _LOGGER.info('Discovery configuration done!')

    # Save config
    if not config_from_file(
            hass.config.path(PLEX_CONFIG_FILE),
            {host: {'token': token}}):
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
            _LOGGER.error(
                'Could not connect to plex server at http://%s', host)
            return

        new_plex_clients = []
        for device in devices:
            # For now, let's allow all deviceClass types
            if device.deviceClass in ['badClient']:
                continue

            if device.machineIdentifier not in plex_clients:
                new_client = PlexClient(device, plex_sessions, update_devices,
                                        update_sessions)
                plex_clients[device.machineIdentifier] = new_client
                new_plex_clients.append(new_client)
            else:
                plex_clients[device.machineIdentifier].set_device(device)

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
            plex_sessions[session.player.machineIdentifier] = session

    update_devices()
    update_sessions()


def request_configuration(host, hass, add_devices_callback):
    """Request configuration steps from the user."""
    configurator = get_component('configurator')

    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[host], 'Failed to register, please try again.')

        return

    def plex_configuration_callback(data):
        """The actions to do when our configuration callback is called."""
        setup_plexserver(host, data.get('token'), hass, add_devices_callback)

    _CONFIGURING[host] = configurator.request_config(
        hass, 'Plex Media Server', plex_configuration_callback,
        description=('Enter the X-Plex-Token'),
        description_image='/static/images/config_plex_mediaserver.png',
        submit_caption='Confirm',
        fields=[{'id': 'token', 'name': 'X-Plex-Token', 'type': ''}]
    )


class PlexClient(MediaPlayerDevice):
    """Representation of a Plex device."""

    # pylint: disable=too-many-public-methods, attribute-defined-outside-init
    def __init__(self, device, plex_sessions, update_devices, update_sessions):
        """Initialize the Plex device."""
        from plexapi.utils import NA

        self.na_type = NA
        self.plex_sessions = plex_sessions
        self.update_devices = update_devices
        self.update_sessions = update_sessions
        self.set_device(device)

    def set_device(self, device):
        """Set the device property."""
        self.device = device

    @property
    def unique_id(self):
        """Return the id of this plex client."""
        return '{}.{}'.format(
            self.__class__, self.device.machineIdentifier or self.device.name)

    @property
    def name(self):
        """Return the name of the device."""
        return self.device.title or DEVICE_DEFAULT_NAME

    @property
    def session(self):
        """Return the session, if any."""
        return self.plex_sessions.get(self.device.machineIdentifier, None)

    @property
    def state(self):
        """Return the state of the device."""
        if self.session and self.session.player:
            state = self.session.player.state
            if state == 'playing':
                return STATE_PLAYING
            elif state == 'paused':
                return STATE_PAUSED
        # This is nasty. Need to find a way to determine alive
        elif self.device:
            return STATE_IDLE
        else:
            return STATE_OFF

        return STATE_UNKNOWN

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
        if self.session is not None:
            return self._convert_na_to_none(self.session.ratingKey)

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self.session is None:
            return None
        media_type = self.session.type
        if media_type == 'episode':
            return MEDIA_TYPE_TVSHOW
        elif media_type == 'movie':
            return MEDIA_TYPE_VIDEO
        elif media_type == 'track':
            return MEDIA_TYPE_MUSIC
        return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self.session is not None:
            return self._convert_na_to_none(self.session.duration)

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self.session is not None:
            thumb_url = self._convert_na_to_none(self.session.thumbUrl)
            if str(self.na_type) in thumb_url:
                # Audio tracks build their thumb urls internally before passing
                # back a URL with the PlexAPI _NA type already converted to a
                # string and embedded into a malformed URL
                thumb_url = None
            return thumb_url

    @property
    def media_title(self):
        """Title of current playing media."""
        # find a string we can use as a title
        if self.session is not None:
            return self._convert_na_to_none(self.session.title)

    @property
    def media_season(self):
        """Season of curent playing media (TV Show only)."""
        from plexapi.video import Show
        if isinstance(self.session, Show):
            return self._convert_na_to_none(self.session.seasons()[0].index)

    @property
    def media_series_title(self):
        """The title of the series of current playing media (TV Show only)."""
        from plexapi.video import Show
        if isinstance(self.session, Show):
            return self._convert_na_to_none(self.session.grandparentTitle)

    @property
    def media_episode(self):
        """Episode of current playing media (TV Show only)."""
        from plexapi.video import Show
        if isinstance(self.session, Show):
            return self._convert_na_to_none(self.session.index)

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_PLEX

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self.device.setVolume(int(volume * 100),
                              self._active_media_plexapi_type)

    def media_play(self):
        """Send play command."""
        self.device.play(self._active_media_plexapi_type)

    def media_pause(self):
        """Send pause command."""
        self.device.pause(self._active_media_plexapi_type)

    def media_stop(self):
        """Send stop command."""
        self.device.stop(self._active_media_plexapi_type)

    def media_next_track(self):
        """Send next track command."""
        self.device.skipNext(self._active_media_plexapi_type)

    def media_previous_track(self):
        """Send previous track command."""
        self.device.skipPrevious(self._active_media_plexapi_type)
