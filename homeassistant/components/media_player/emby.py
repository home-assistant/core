"""
Support to interface with the Emby API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.emby/
"""
import json
import logging
import os
from datetime import timedelta
from urllib.request import Request, urlopen
from urllib.parse import urlparse

import homeassistant.util as util
from homeassistant.components.media_player import (
    MEDIA_TYPE_TVSHOW, MEDIA_TYPE_VIDEO, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, 
    SUPPORT_SEEK, SUPPORT_STOP, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_PREVIOUS_TRACK, MediaPlayerDevice)
from homeassistant.const import (
    DEVICE_DEFAULT_NAME, STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING,
    STATE_UNKNOWN)
from homeassistant.loader import get_component
from homeassistant.helpers.event import (track_utc_time_change)

REQUIREMENTS = []
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)

EMBY_CONFIG_FILE = 'emby.conf'

# Map ip to request id for configuring
_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

SUPPORT_EMBY = SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | SUPPORT_STOP | SUPPORT_SEEK


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
    """Setup the Emby platform."""
    config = config_from_file(hass.config.path(EMBY_CONFIG_FILE))
    if len(config):
        # Setup a configured EmbyServer
        host, token = config.popitem()
        token = token['token']
    else:
        return

    setup_embyserver(host, token, hass, add_devices_callback)


# pylint: disable=too-many-branches
def setup_embyserver(host, token, hass, add_devices_callback):
    _LOGGER.info('Setting up Emby server at: ' + host)
    """Setup a embyserver based on host parameter."""
    embyserver = EmbyRemote(token, host)
    
    # If we came here and configuring this host, mark as done
    if host in _CONFIGURING:
        request_id = _CONFIGURING.pop(host)
        configurator = get_component('configurator')
        configurator.request_done(request_id)
        _LOGGER.info('Discovery configuration done!')

    # Save config
    if not config_from_file(
            hass.config.path(EMBY_CONFIG_FILE),
            {host: {'token': token}}):
        _LOGGER.error('failed to save config file')

    _LOGGER.info('Connected to: %s', host)

    emby_clients = {}
    emby_sessions = {}
    track_utc_time_change(hass, lambda now: update_devices(), second=30)

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_devices():
        """Update the devices objects."""
        try:
            devices = embyserver.getSessions()
        except OSError:
            _LOGGER.error(
                'Could not connect to emby server at %s', host)
            return

        new_emby_clients = []
        for device in devices:
            # For now, let's allow all deviceClass types
            if not device['SupportsRemoteControl']:
                continue

            if device['DeviceId'] not in emby_clients:
                new_client = EmbyClient(embyserver, device, emby_sessions, update_devices, update_sessions)
                emby_clients[device['DeviceId']] = new_client
                new_emby_clients.append(new_client)
            else:
                emby_clients[device['DeviceId']].set_device(device)

        if new_emby_clients:
            add_devices_callback(new_emby_clients)

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_sessions():
        """Update the sessions objects."""
        try:
            sessions = embyserver.getSessions()
        except:
            _LOGGER.exception('Error listing emby sessions')
            return

        emby_sessions.clear()
        for session in sessions:
            if not session['SupportsRemoteControl']:
                continue
            emby_sessions[session['DeviceId']] = session

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

    def emby_configuration_callback(data):
        """The actions to do when our configuration callback is called."""
        setup_embyserver(host, data.get('token'), hass, add_devices_callback)


class EmbyRemote:
    @property
    def getSessionsUrl(self):
        """Return the session url."""
        return self.serverUrl + 'Sessions?api_key={0}'
    
    @property
    def playstateUrl(self):
        return self.serverUrl + 'emby/Sessions/{0}/Playing/{1}?api_key={2}'
    
    @property
    def getImageUrl(self):
        return self.serverUrl + 'Items/{0}/Images/{1}?api_key={2}'
    
    def __init__(self, apiKey, serverUrl):
        self.apiKey = apiKey
        self.serverUrl = serverUrl
    def getSessions(self):
        url = self.getSessionsUrl.format(self.apiKey)
        request = Request(url)
        request.add_header('Content-Type', 'application/json')
        request.add_header('Accept', 'application/json')
        response = urlopen(request).read().decode('utf-8')
        clients = json.loads(response)
        return clients

    def setPlaystate(self, session, state):
        request = Request(self.playstateUrl.format(session['Id'], state, self.apiKey), None, {}, None, False, 'POST')
        request.add_header('Content-Type', 'application/json')
        request.add_header('Accept', 'application/json')
        request.add_header('x-emby-authorization', 'MediaBrowser Client="Emby Mobile", Device="Chrome 51.0.2704.103", DeviceId="2d9cfa55b954073d05fbd3cd993ab244", Version="3.0.6020.0"')
        response = urlopen(request).read().decode('utf-8')

    def play(self, session):
        self.setPlaystate(session, 'unpause')
    def pause(self, session):
        self.setPlaystate(session, 'pause')
    def stop(self, session):
        self.setPlaystate(session, 'stop')
    def next_track(self, session):
        self.setPlaystate(session, 'nexttrack')
    def previous_track(self, session):
        self.setPlaystate(session, 'previoustrack')


    def getImage(self, itemId, type):
        return self.getImageUrl.format(itemId, type, self.apiKey)

class EmbyClient(MediaPlayerDevice):
    """Representation of a Emby device."""

    # pylint: disable=too-many-public-methods, attribute-defined-outside-init
    def __init__(self, client, device, emby_sessions, update_devices, update_sessions):
        """Initialize the Emby device."""
        self.emby_sessions = emby_sessions
        self.update_devices = update_devices
        self.update_sessions = update_sessions
        self.client = client
        self.set_device(device)

    def set_device(self, device):
        """Set the device property."""
        self.device = device

    @property
    def unique_id(self):
        """Return the id of this emby client."""
        return '{}.{}'.format(
            self.__class__, self.device['DeviceId'] or self.device['DeviceName'])

    @property
    def name(self):
        """Return the name of the device."""
        return self.device['DeviceName'] or DEVICE_DEFAULT_NAME

    @property
    def session(self):
        """Return the session, if any."""
        if self.device['DeviceId'] not in self.emby_sessions:
            return None

        return self.emby_sessions[self.device['DeviceId']]

    @property
    def now_playing_item(self):
        """Return the currently playing item, if any."""
        session = self.session
        if session is not None and 'NowPlayingItem' in session:
            return session['NowPlayingItem']

    @property
    def state(self):
        """Return the state of the device."""
        session = self.session
        if session:
            if 'NowPlayingItem' in session:
                if session['PlayState']['IsPaused']:
                    return STATE_PAUSED
                else:
                    return STATE_PLAYING
            else: return STATE_IDLE
        # This is nasty. Need to find a way to determine alive
        else:
            return STATE_OFF

        return STATE_UNKNOWN

    def update(self):
        """Get the latest details."""
        self.update_devices(no_throttle=True)
        self.update_sessions(no_throttle=True)

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        if self.now_playing_item is not None:
            return self.now_playing_item['Id']

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self.now_playing_item is None:
            return None
        media_type = self.now_playing_item['Type']
        if media_type == 'Episode':
            return MEDIA_TYPE_TVSHOW
        elif media_type == 'Movie':
            return MEDIA_TYPE_VIDEO
        return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self.now_playing_item is not None:
            return int(self.now_playing_item['RunTimeTicks']) / 10000000

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self.now_playing_item is not None:
            return self.client.getImage(self.now_playing_item['Id'], 'Thumb')

    @property
    def media_title(self):
        """Title of current playing media."""
        # find a string we can use as a title
        if self.now_playing_item is not None:
            return self.now_playing_item['Name']

    @property
    def media_season(self):
        """Season of curent playing media (TV Show only)."""
        if self.now_playing_item is not None and 'ParentIndexNumber' in self.now_playing_item:
            return self.now_playing_item['ParentIndexNumber']

    @property
    def media_series_title(self):
        """The title of the series of current playing media (TV Show only)."""
        if self.now_playing_item is not None and 'SeriesName' in self.now_playing_item:
            return self.now_playing_item['SeriesName']

    @property
    def media_episode(self):
        """Episode of current playing media (TV Show only)."""
        if self.now_playing_item is not None and 'IndexNumber' in self.now_playing_item:
            return self.now_playing_item['IndexNumber']

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_EMBY

    def media_play(self):
        """Send play command."""
        self.client.play(self.session)

    def media_pause(self):
        """Send pause command."""
        self.client.pause(self.session)

    def media_next_track(self):
        """Send next track command."""
        self.client.next_track(self.session)

    def media_previous_track(self):
        """Send previous track command."""
        self.client.previous_track(self.session)
