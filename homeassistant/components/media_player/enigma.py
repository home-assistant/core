"""
Support for Enigma2 set-top boxes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/enigma/
"""
#
# For more details, please refer to github at
# https://github.com/cinzas/homeassistant-enigma-player
#
# This is a branch from
# https://github.com/KavajNaruj/homeassistant-enigma-player
#

# Imports and dependencies
import asyncio
from datetime import timedelta
from urllib.error import HTTPError, URLError
import urllib.parse
import urllib.request

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_CHANNEL, MEDIA_TYPE_TVSHOW, SUPPORT_NEXT_TRACK, SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP, MediaPlayerDevice)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.components.enigma import _LOGGER, DOMAIN as ENIGMA_DOMAIN
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

# From homeassitant


# Dependencies
DEPENDENCIES = ['enigma']

# DEFAULTS
DEFAULT_PORT = 80
DEFAULT_NAME = "Enigma2 Satelite"
DEFAULT_TIMEOUT = 30
DEFAULT_USERNAME = 'root'
DEFAULT_PASSWORD = ''
DEFAULT_BOUQUET = 'bouquet'
DEFAULT_PICON = 'picon'

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=5)

SUPPORT_ENIGMA = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                 SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
                 SUPPORT_SELECT_SOURCE | SUPPORT_NEXT_TRACK | \
                 SUPPORT_PREVIOUS_TRACK | SUPPORT_VOLUME_STEP | \
                 SUPPORT_PLAY | SUPPORT_PLAY_MEDIA

MAX_VOLUME = 100


# SETUP PLATFORM
async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Initialize the Enigma device."""
    devices = []
    enigma_list = hass.data[ENIGMA_DOMAIN]

    for device in enigma_list:
        _LOGGER.debug("Configured a new EnigmaMediaPlayer %s",
                      device.get_host)
        devices.append(EnigmaMediaPlayer(device))

    async_add_devices(devices, update_before_add=True)


# Enigma Media Player Device
class EnigmaMediaPlayer(MediaPlayerDevice):
    """Representation of a Enigma Media Player device."""

    def __init__(self, EnigmaMediaPlayerDevice):
        """Initialize the Enigma device."""
        self._host = EnigmaMediaPlayerDevice.get_host
        self._port = EnigmaMediaPlayerDevice.get_port
        self._name = EnigmaMediaPlayerDevice.get_name
        self._username = EnigmaMediaPlayerDevice.get_username
        self._password = EnigmaMediaPlayerDevice.get_password
        self._timeout = EnigmaMediaPlayerDevice.get_timeout
        self._bouquet = EnigmaMediaPlayerDevice.get_bouquet
        self._picon = EnigmaMediaPlayerDevice.get_picon
        self._opener = EnigmaMediaPlayerDevice.get_opener
        self._pwstate = True
        self._volume = 0
        self._muted = False
        self._selected_source = ''
        self._picon_url = None
        self._source_names = {}
        self._sources = {}
        self.load_sources()

    # Load channels from specified bouquet orfrom first available bouquet
    def load_sources(self):
        """Initialize the Enigma device loading the sources."""
        from bs4 import BeautifulSoup

        if self._bouquet:
            # Load user set bouquet.
            _LOGGER.debug("Enigma: [load_sources] - Request user bouquet %s ",
                          self._bouquet)
            epgbouquet_xml = self.request_call('/web/epgnow?bRef=' +
                                               urllib.parse.quote_plus
                                               (self._bouquet))

            # Channels name
            soup = BeautifulSoup(epgbouquet_xml, 'html.parser')
            src_names = soup.find_all('e2eventservicename')
            self._source_names = [src_name.string for src_name in src_names]
            # Channels reference
            src_references = soup.find_all('e2eventservicereference')
            sources = [src_reference.string for src_reference in
                       src_references]
            self._sources = dict(zip(self._source_names, sources))

        else:
            # Load sources from first bouquet.
            reference = urllib.parse.quote_plus(self.get_bouquet_reference())
            _LOGGER.debug("Enigma: [load_sources] - Request reference %s ",
                          reference)
            epgbouquet_xml = self.request_call('/web/epgnow?bRef=' + reference)

            # Channels name
            soup = BeautifulSoup(epgbouquet_xml, 'html.parser')
            src_names = soup.find_all('e2eventservicename')
            self._source_names = [src_name.string for src_name in src_names]

            # Channels reference
            src_references = soup.find_all('e2eventservicereference')
            sources = [src_reference.string for src_reference in
                       src_references]
            self._sources = dict(zip(self._source_names, sources))

    def get_bouquet_reference(self):
        """Import BeautifulSoup."""
        from bs4 import BeautifulSoup
        # Get first bouquet reference
        bouquets_xml = self.request_call('/web/getallservices')
        # bouquets_xml = self.request_call('/web/bouquets')
        soup = BeautifulSoup(bouquets_xml, 'html.parser')
        return soup.find('e2servicereference').renderContents().decode('UTF8')

    # API requests
    def request_call(self, url):
        """Call web API request."""
        uri = 'http://' + self._host + ":" + str(self._port) + url
        _LOGGER.debug("Enigma: [request_call] - Call request %s ", uri)
        try:
            return self._opener.open(uri, timeout=self._timeout).read()
        except (HTTPError, URLError, ConnectionRefusedError):
            _LOGGER.exception("Enigma: [request_call] - Error connecting to \
                              remote enigma %s: %s ", self._host,
                              HTTPError.code)
        return False

    # Component Update
    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def update(self):
        """Import BeautifulSoup."""
        from bs4 import BeautifulSoup
        # Get the latest details from the device.
        _LOGGER.info("Enigma: [update] - request for host %s (%s)", self._host,
                     self._name)
        powerstate_xml = self.request_call('/web/powerstate')

        powerstate_soup = BeautifulSoup(powerstate_xml, 'html.parser')
        pwstate = powerstate_soup.e2instandby.renderContents().decode('UTF8')
        self._pwstate = ''

        _LOGGER.debug("Enigma: [update] - Powerstate for host %s = %s",
                      self._host, pwstate)
        if pwstate.find('false') >= 0:
            self._pwstate = 'false'

        if pwstate.find('true') >= 0:
            self._pwstate = 'true'

        # If name was not defined, get the name from the box
        if self._name == 'Enigma2 Satelite':
            about_xml = self.request_call('/web/about')
            soup = BeautifulSoup(about_xml, 'html.parser')
            name = soup.e2model.renderContents().decode('UTF8')
            _LOGGER.debug("Enigma: [update] - Name for host %s = %s",
                          self._host, name)
            if name:
                self._name = name

        # If powered on
        if self._pwstate == 'false':
            subservices_xml = self.request_call('/web/subservices')
            soup = BeautifulSoup(subservices_xml, 'html.parser')
            servicename = soup.e2servicename.renderContents().decode('UTF8')
            reference = soup.e2servicereference.renderContents().decode('UTF8')

            eventtitle = 'N/A'
            # If we got a valid reference, check the title of the event and
            # the picon url
            if reference != '' and reference != 'N/A' and \
                            not reference.startswith('1:0:0:0:0:0:0:0:0:0:'):
                xml = self.request_call('/web/epgservicenow?sRef=' + reference)
                soup = BeautifulSoup(xml, 'html.parser')
                eventtitle = soup.e2eventtitle.renderContents().decode('UTF8')
                if self._password != DEFAULT_PASSWORD:
                    # if icon = screenhost then get screenshot
                    if self._picon == 'screenshot':
                        self._picon_url = 'http://' + \
                                           self._username + ':' + \
                                           self._password + \
                                           '@' + self._host + ':' + \
                                           str(self._port) + '/grab?format=png\
                                           &r=720&mode=all&reference=' + \
                                           reference.replace(":", "_")[:-1]
                    # otherwise try to get picon
                    else:
                        self._picon_url = 'http://' + \
                                           self._username + ':' + \
                                           self._password + \
                                           '@' + self._host + ':' + \
                                           str(self._port) + '/picon/' + \
                                           reference.replace(":", "_")[:-1] \
                                           + '.png'
                else:
                    # if icon = screenhost then get screenshot
                    if self._picon == 'screenshot':
                        self._picon_url = 'http://' + \
                                           self._username + ':' + \
                                           self._password + \
                                           '@' + self._host + ':' + \
                                           str(self._port) + '/grab?format=png\
                                           &r=720&mode=all&reference=' + \
                                           reference.replace(":", "_")[:-1]
                    # otherwise try to get picon
                    else:
                        self._picon_url = 'http://' + self._host + ':' + \
                                           str(self._port) + '/picon/' + \
                                           reference.replace(":", "_")[:-1] \
                                           + '.png'
            _LOGGER.debug("Enigma: [update] - Eventtitle for host %s = %s",
                          self._host, eventtitle)

            # Check volume and if is muted and update self variables
            volume_xml = self.request_call('/web/vol')
            soup = BeautifulSoup(volume_xml, 'html.parser')
            volcurrent = soup.e2current.renderContents().decode('UTF8')
            volmuted = soup.e2ismuted.renderContents().decode('UTF8')

            self._volume = int(volcurrent) / MAX_VOLUME if volcurrent else None
            self._muted = (volmuted == 'True') if volmuted else None
            _LOGGER.debug("Enigma: [update] - Volume for host %s = %s",
                          self._host, volcurrent)
            _LOGGER.debug("Enigma: [update] - Is host %s muted = %s",
                          self._host, volmuted)

            # Concatenate Channel and Title name to display
            self._selected_source = (servicename + ' - ' + eventtitle)
        return True

# GET - Name
    @property
    def name(self):
        """Return the name of the device."""
        return self._name

# GET - State
    @property
    def state(self):
        """Return the state of the device."""
        if self._pwstate == 'true':
            return STATE_OFF
        if self._pwstate == 'false':
            return STATE_ON

        return STATE_UNKNOWN

# GET - Volume Level
    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

# GET - Muted
    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

# GET - Features
    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        return SUPPORT_ENIGMA

# GET - Content type
    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_TVSHOW

# GET - Content id - Current Channel name
    @property
    def media_content_id(self):
        """Service Ref of current playing media."""
        return self._selected_source

# GET - Media title - Current Channel name
    @property
    def media_title(self):
        """Title of current playing media."""
        return self._selected_source

# GET - Content picon - Current Channel Picon
# /picon directory must exist in enigma2 box (use symlink if not)
    @property
    def media_image_url(self):
        """Title of current playing media."""
        _LOGGER.debug("Enigma: [media_image_url] - %s", self._picon_url)
        return self._picon_url

# GET - Current channel - Current Channel Name
    @property
    def source(self):
        """Return the current input source."""
        return self._selected_source

# GET - Channel list - Channel names from current bouquet
    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

# SET - Change channel - From dropbox menu
    @asyncio.coroutine
    def async_select_source(self, source):
        """Select input source."""
        _LOGGER.debug("Enigma: [async_select_source] - Change source channel")
        self.request_call('/web/zap?sRef=' + self._sources[source])

# SET - Volume up
    @asyncio.coroutine
    def async_volume_up(self):
        """Set volume level up."""
        self.request_call('/web/vol?set=up')

# SET - Volume down
    @asyncio.coroutine
    def async_volume_down(self):
        """Set volume level down."""
        self.request_call('/web/vol?set=down')

# SET - Volume level
    @asyncio.coroutine
    def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        volset = str(round(volume * MAX_VOLUME))
        self.request_call('/web/vol?set=set' + volset)

# SET - Volume mute
    @asyncio.coroutine
    def async_mute_volume(self, mute):
        """Mute or unmute media player."""
        self.request_call('/web/vol?set=mute')

# SET - Change to channel number
    @asyncio.coroutine
    def async_play_media(self, media_type, media_id, **kwargs):
        """Support changing a channel."""
        if media_type != MEDIA_TYPE_CHANNEL:
            _LOGGER.error('Unsupported media type')
            return
        try:
            cv.positive_int(media_id)
        except vol.Invalid:
            _LOGGER.error('Media ID must be positive integer')
            return
        # Hack to map remote key press
        # 2   Key "1"
        # 3   Key "2"
        # 4   Key "3"
        # 5   Key "4"
        # 6   Key "5"
        # 7   Key "6"
        # 8   Key "7"
        # 9   Key "8"
        # 10  Key "9"
        # 11  Key "0"
        for digit in media_id:
            if digit == '0':
                channel_digit = '11'
            else:
                channel_digit = int(digit)+1
            self.request_call('/web/remotecontrol?command='+str(channel_digit))

# SET - Turn on
    @asyncio.coroutine
    def async_turn_on(self):
        """Turn the media player on."""
        self.request_call('/web/powerstate?newstate=4')
        self.update()

# SET - Turn of
    @asyncio.coroutine
    def async_turn_off(self):
        """Turn off media player."""
        self.request_call('/web/powerstate?newstate=5')

# SET - Next channel
    @asyncio.coroutine
    def async_media_next_track(self):
        """Change to next channel."""
        self.request_call('/web/remotecontrol?command=106')

# SET - Previous channel
    @asyncio.coroutine
    def async_media_previous_track(self):
        """Change to previous channel."""
        self.request_call('/web/remotecontrol?command=105')
