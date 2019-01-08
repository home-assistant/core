"""
Support for Playstation 4.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.ps4/
"""
from datetime import timedelta
import logging
import socket

import voluptuous as vol

import homeassistant.util as util
from homeassistant.components.media_player import (
    ENTITY_IMAGE_URL, MEDIA_TYPE_MUSIC, MediaPlayerDevice, PLATFORM_SCHEMA,
    SUPPORT_SELECT_SOURCE, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_IDLE, STATE_OFF, STATE_PLAYING,
    STATE_UNKNOWN,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['pyps4-homeassistant==0.1.7']

_CONFIGURING = {}
PLATFORM = 'PS4'
NOTIFICATION_TITLE = 'PS4 Setup'
NOTIFICATION_TITLE_PAIR = 'Pair PS4'
_LOGGER = logging.getLogger(__name__)

SUPPORT_PS4 = SUPPORT_TURN_OFF | SUPPORT_TURN_ON | \
    SUPPORT_STOP | SUPPORT_SELECT_SOURCE

DEFAULT_NAME = "Playstation 4"
ICON = 'mdi:playstation'
GAMES_FILE = '.ps4-games.json'
MEDIA_IMAGE_DEFAULT = None
CONFIG_FILE = '.ps4.conf'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def request_configuration(hass, config, add_devices, _creds):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator
    host = config.get(CONF_HOST)

    def connect_callback(data):
        """Run after creds are saved. Pair with PS4."""
        import pyps4_homeassistant as pyps4
        pin = data.get('pin')
        if len(pin) != 8:
            configurator.notify_errors(_CONFIGURING[host],
                                       "Invalid PIN Code")
        cred_file = load_json(hass.config.path(CONFIG_FILE))
        creds = cred_file[host]
        ps4 = pyps4.Ps4(host, creds)
        try:
            ps4.login(pin)
        except socket.error:
            configurator.notify_errors(_CONFIGURING[host],
                                       "Socket Error")
        else:
            setup_platform(hass, config, add_devices, discovery_info=None)

    def configuration_callback(data):
        """Run when the configuration callback is called."""
        result = credentials.listen()
        if result is None:
            configurator.notify_errors(_CONFIGURING[host],
                                       "Could not fetch credentials")
        else:
            cred_file = hass.config.path(CONFIG_FILE)
            try:
                cred = {host: result}
                save_json(cred_file, cred)
                hass.components.configurator.request_done(
                    _CONFIGURING.pop(host))
            except OSError:
                _LOGGER.error("Could not save credentials file")
            _CONFIGURING[host] = configurator.request_config(
                NOTIFICATION_TITLE_PAIR, connect_callback,
                description="On PS4 go to settings > Mobile App Settings > Add Device\
                and enter PIN that is displayed",
                submit_caption='Enter',
                fields=[{
                    'id': 'pin',
                    'name': 'PIN',
                    'type': 'string'}]
            )

    if host not in _CONFIGURING:
        credentials = _creds

    _CONFIGURING[host] = configurator.request_config(
        NOTIFICATION_TITLE, configuration_callback,
        description="Press start to begin config. Then\
        in PS4 Second Screen App, refresh devices and select 'Home-Assistant'",
        submit_caption='Start'
    )


def get_credentials(hass, config):
    """Get credentials if any."""
    host = config.get(CONF_HOST)
    creds_file = hass.config.path(CONFIG_FILE)
    try:
        creds = load_json(creds_file)
        credentials = creds[host]
    except KeyError:
        credentials = None
        _LOGGER.debug("No credentials found for %s", (host))
    return credentials


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the PS4 platform."""
    import pyps4_homeassistant as pyps4
    host = config.get(CONF_HOST)
    creds = None
    creds = get_credentials(hass, config)
    if creds is not None:
        if host in _CONFIGURING:
            hass.components.configurator.request_done(_CONFIGURING.pop(host))
        name = config.get(CONF_NAME)
        ps4 = pyps4.Ps4(host, creds)
        games_file = hass.config.path(GAMES_FILE)
        add_devices([PS4Device(name, host, ps4, games_file)], True)
    elif creds is None:
        _creds = pyps4.Credentials()
        request_configuration(hass, config, add_devices, _creds)
        return True


class PS4Device(MediaPlayerDevice):
    """Representation of a PS4."""

    def __init__(self, name, host, ps4, games_file):
        """Initialize the ps4 device."""
        self._ps4 = ps4
        self._host = host
        self._name = name
        self._state = STATE_UNKNOWN
        self._games_filename = games_file
        self._media_content_id = None
        self._media_title = None
        self._media_image = None
        self._source = None
        self._games = self.load_games()
        self._source_list = list(sorted(self._games.values()))

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Retrieve the latest data."""
        try:
            status = self._ps4.get_status()
        except socket.timeout:
            self._state = STATE_UNKNOWN
            return
        if status is not None:
            if status.get('status') == 'Ok':
                titleid = status.get('running-app-titleid')
                name = status.get('running-app-name')
                if titleid and name is not None:
                    self._state = STATE_PLAYING
                    if self._media_content_id != titleid:
                        self._media_content_id = titleid
                        app_name, art = self._ps4.get_ps_store_data(name)
                        self._media_title = app_name or name
                        self._source = self._media_title
                        self._media_image = art
                        if titleid in self._games:
                            store = self._games[titleid]
                            if store != app_name:
                                self._games.pop(titleid)
                        if titleid not in self._games:
                            self.add_games(titleid, app_name)
                            self._games = self.load_games()
                        self._source_list = list(sorted(self._games.values()))
                else:
                    self.idle()
        else:
            self.state_off()

    def idle(self):
        """Set states for state idle."""
        self.no_title()
        self._state = STATE_IDLE

    def state_off(self):
        """Set states for state off."""
        self.no_title()
        self._state = STATE_OFF

    def no_title(self):
        """Update if there is no title."""
        self._media_title = None
        self._media_content_id = None
        self._source = None

    def load_games(self):
        """Load games for sources."""
        file = self._games_filename
        try:
            games = load_json(file)
            return games
        except FileNotFoundError:
            games = {}
            self.save_games(games)
            self.load_games()

    def save_games(self, games):
        """Save games to file."""
        file = self._games_filename
        try:
            save_json(file, games)
        except OSError as error:
            _LOGGER.error("Could not save game list, %s", error)

    def add_games(self, titleid, app_name):
        """Add games to list."""
        games = self.load_games()
        if titleid is not None and titleid not in games:
            game = {titleid: app_name}
            games.update(game)
            self.save_games(games)

    @property
    def entity_picture(self):
        """Return picture."""
        if self._state == STATE_OFF:
            return None

        image_hash = self.media_image_hash
        if image_hash is not None:
            return ENTITY_IMAGE_URL.format(
                self.entity_id, self.access_token, image_hash)

        if self._media_content_id is None:
            return None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Icon."""
        return ICON

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._media_content_id

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self._media_content_id is None:
            return MEDIA_IMAGE_DEFAULT
        try:
            return self._media_image
        except KeyError:
            return MEDIA_IMAGE_DEFAULT

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._media_title

    @property
    def supported_features(self):
        """Media player features that are supported."""
        return SUPPORT_PS4

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    def turn_off(self):
        """Turn off media player."""
        self._ps4.standby()

    def turn_on(self):
        """Turn on the media player."""
        self._ps4.wakeup()

    def media_pause(self):
        """Send keypress ps to return to menu."""
        self._ps4.remote_control('ps')

    def media_stop(self):
        """Send keypress ps to return to menu."""
        self._ps4.remote_control('ps')

    def select_source(self, source):
        """Select input source."""
        for title_id, game in self._games.items():
            if source == game:
                _LOGGER.debug(
                    "Starting PS4 game %s (%s) using source %s",
                    game, title_id, source)
                self._ps4.start_title(title_id)
                return
