"""
homeassistant.components.media_player.plex
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides an interface to the Plex API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.plex.html
"""
import logging
from datetime import timedelta
from urllib.parse import urlparse

from homeassistant.loader import get_component
import homeassistant.util as util
from homeassistant.components.media_player import (
    MediaPlayerDevice, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_NEXT_TRACK, MEDIA_TYPE_TVSHOW, MEDIA_TYPE_VIDEO)
from homeassistant.const import (
    CONF_HOST, DEVICE_DEFAULT_NAME, STATE_IDLE, STATE_PLAYING,
    STATE_PAUSED, STATE_OFF, STATE_UNKNOWN)

REQUIREMENTS = ['plexapi==1.1.0']
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)

PLEX_CONFIG_FILE = 'plex.conf'

# Map ip to request id for configuring
_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

SUPPORT_PLEX = SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK


# pylint: disable=abstract-method, unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Sets up the plex platform. """

    if discovery_info is not None:
        # Parse discovery data
        host = urlparse(discovery_info[1]).netloc
        _LOGGER.info('Discovered PLEX server: %s'%host)
    else:
        host = config.get(CONF_HOST, None)

    if host in _CONFIGURING:
        return

    setup_plexserver(host, hass, add_devices_callback)


def setup_plexserver(host, hass, add_devices_callback):
    ''' Setup a plexserver based on host parameter'''
    import plexapi

    # Config parsing & discovery mix
    conf_file = hass.config.path(PLEX_CONFIG_FILE)
    try:
        with open(conf_file,'r') as f:
            conf_dict = eval(f.read())
    except IOError: # File not found
        if host == None:
            # No discovery, no config, quit here
            return
        conf_dict = {}

    if host == None:
        # Called by module inclusion, let's only use config
        host,token = conf_dict.popitem()
        token = token['token']
    elif host not in conf_dict.keys():
        # Not in config
        conf_dict[host] = { 'token' : '' }
        token = None

    _LOGGER.info('Connecting to: htts://%s using token: %s' %
            (host, token))
    try:
        plexserver = plexapi.PlexServer('http://%s'%host, token)
    except Exception:
        request_configuration(host, hass, add_devices_callback)
        return
    except plexapi.exceptions.BadRequest as e:
        _LOGGER.error('BLABLA1')
        request_configuration(host, hass, add_devices_callback)
        return

    _LOGGER.info('Connected to: htts://%s using token: %s' %
            (host, token))

    plex_clients = {}
    plex_sessions = {}

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_devices():
        """ Updates the devices objects. """
        try:
            devices = plexserver.clients()
        except BadRequest:
            _LOGGER.exception("Error listing plex devices")
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
            add_devices(new_plex_clients)

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_sessions():
        """ Updates the sessions objects. """
        try:
            sessions = plexserver.sessions()
        except BadRequest:
            _LOGGER.exception("Error listing plex sessions")
            return

        plex_sessions.clear()
        for session in sessions:
            plex_sessions[session.player.machineIdentifier] = session

    update_devices()
    update_sessions()


def request_configuration(host, hass, add_devices_callback):
    """ Request configuration steps from the user. """
    configurator = get_component('configurator')

    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[host], "Failed to register, please try again.")

        return

    def plex_configuration_callback(data):
        """ Actions to do when our configuration callback is called. """
        setup_plexserver(host, hass, add_devices_callback)

    _CONFIGURING[host] = configurator.request_config(
        hass, "Plex Media Server", plex_configuration_callback,
        description=('Enter the X-Plex-Token'),
        description_image="/static/images/config_plex_mediaserver.png",
        submit_caption="Confirm",
        fields=[{'Token':'token'}]
    )


class PlexClient(MediaPlayerDevice):
    """ Represents a Plex device. """

    # pylint: disable=too-many-public-methods
    def __init__(self, device, plex_sessions, update_devices, update_sessions):
        self.plex_sessions = plex_sessions
        self.update_devices = update_devices
        self.update_sessions = update_sessions
        self.set_device(device)

    def set_device(self, device):
        """ Sets the device property. """
        self.device = device

    @property
    def session(self):
        """ Returns the session, if any. """
        if self.device.machineIdentifier not in self.plex_sessions:
            return None

        return self.plex_sessions[self.device.machineIdentifier]

    @property
    def name(self):
        """ Returns the name of the device. """
        return self.device.name or self.device.product or self.device.device

    @property
    def state(self):
        """ Returns the state of the device. """
        if self.session:
            state = self.session.player.state
            if state == 'playing':
                return STATE_PLAYING
            elif state == 'paused':
                return STATE_PAUSED
        # This is nasty. Need ti find a way to determine alive
        elif self.device:
            return STATE_IDLE
        else:
            return STATE_OFF

        return STATE_UNKNOWN

    def update(self):
        self.update_devices(no_throttle=True)
        self.update_sessions(no_throttle=True)

    @property
    def media_content_id(self):
        """ Content ID of current playing media. """
        if self.session is not None:
            return self.session.ratingKey

    @property
    def media_content_type(self):
        """ Content type of current playing media. """
        if self.session is None:
            return None
        media_type = self.session.type
        if media_type == 'episode':
            return MEDIA_TYPE_TVSHOW
        elif media_type == 'movie':
            return MEDIA_TYPE_VIDEO
        return None

    @property
    def media_duration(self):
        """ Duration of current playing media in seconds. """
        if self.session is not None:
            return self.session.duration

    @property
    def media_image_url(self):
        """ Image url of current playing media. """
        if self.session is not None:
            return self.session.thumbUrl

    @property
    def media_title(self):
        """ Title of current playing media. """
        # find a string we can use as a title
        if self.session is not None:
            return self.session.title

    @property
    def media_season(self):
        """ Season of curent playing media (TV Show only). """
        from plexapi.video import Show
        if isinstance(self.session, Show):
            return self.session.seasons()[0].index

    @property
    def media_series_title(self):
        """ Series title of current playing media (TV Show only). """
        from plexapi.video import Show
        if isinstance(self.session, Show):
            return self.session.grandparentTitle

    @property
    def media_episode(self):
        """ Episode of current playing media (TV Show only). """
        from plexapi.video import Show
        if isinstance(self.session, Show):
            return self.session.index

    @property
    def supported_media_commands(self):
        """ Flags of media commands that are supported. """
        return SUPPORT_PLEX

    def media_play(self):
        """ media_play media player. """
        self.device.play()

    def media_pause(self):
        """ media_pause media player. """
        self.device.pause()

    def media_next_track(self):
        """ Send next track command. """
        self.device.skipNext()

    def media_previous_track(self):
        """ Send previous track command. """
        self.device.skipPrevious()
