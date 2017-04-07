"""
Support for Enigma2 Settopboxes

"""
import logging
import urllib.request
import urllib.parse

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_SELECT_SOURCE, MediaPlayerDevice, PLATFORM_SCHEMA,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET)

from homeassistant.const import (
    CONF_HOST, STATE_OFF, STATE_ON, STATE_UNKNOWN, CONF_NAME, CONF_PORT,
    CONF_USERNAME, CONF_PASSWORD, CONF_TIMEOUT)

REQUIREMENTS = ['beautifulsoup4==4.5.1']

from homeassistant.util import Throttle
from datetime import timedelta
from bs4 import BeautifulSoup

import homeassistant.helpers.config_validation as cv

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

DEFAULT_NAME = 'Enigma2 Satelite'
DEFAULT_PORT = 80
DEFAULT_TIMEOUT = None
DEFAULT_USERNAME = 'root'
DEFAULT_PASSWORD = 'password'

SUPPORT_ENIGMA = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                 SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
                 SUPPORT_SELECT_SOURCE

MAX_VOLUME = 100

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.socket_timeout,
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Enigma platform."""
    enigma = EnigmaDevice(config.get(CONF_NAME),
                          config.get(CONF_HOST),
                          config.get(CONF_PORT),
                          config.get(CONF_USERNAME),
                          config.get(CONF_PASSWORD),
                          config.get(CONF_TIMEOUT))
    if enigma.update():
        add_devices([enigma])
        return True
    return False

class EnigmaDevice(MediaPlayerDevice):
    """Representation of a Enigma device."""

    def __init__(self, name, host, port, username, password, timeout):
        """Initialize the Enigma device."""
        self._name = name
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._timeout = timeout
        self._pwstate = True
        self._volume = 0
        self._muted = False
        self._selected_source = ''
        self._source_names = {}
        self._sources = {}
        self.__handle_base_auth()
        self.__load_sources()

    def __handle_base_auth(self):
        """Handle HTTP Auth"""
        password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, self._host, self._username, self._password)
        handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
        opener = urllib.request.build_opener(handler)
        urllib.request.install_opener(opener)

    def __load_sources(self):
        """Load sources from first bouquet"""
        bouquet_reference = self.__get_bouquet_reference()
        try:
            epgbouquet_xml = self.__requestCall('/web/epgnow?bRef=' + urllib.parse.quote_plus(bouquet_reference))
        except (HTTPError, URLError, ConnectionRefusedError):
            return False
        epgbouquet_soup = BeautifulSoup(epgbouquet_xml, 'html.parser')
        service_names = epgbouquet_soup.find_all('e2eventservicename')
        self._source_names = [service_name.string for service_name in service_names]
        service_references = epgbouquet_soup.find_all('e2eventservicereference')
        sources = [service_reference.string for service_reference in service_references]
        self._sources = dict(zip(self._source_names, sources))

    def __get_bouquet_reference(self):
        """Get first bouquet reference"""
        try:
            bouquets_xml = self.__requestCall('/web/bouquets')
        except (HTTPError, URLError, ConnectionRefusedError):
            return False
        bouquets_soup = BeautifulSoup(bouquets_xml, 'html.parser')
        return bouquets_soup.find('e2servicereference').renderContents().decode('UTF8')

    def __requestCall(self, url):
        return urllib.request.urlopen('http://' + self._host + url, timeout = 10).read().decode('UTF8')

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def update(self):
        """Get the latest details from the device."""
        try:
            powerstate_xml = self.__requestCall('/web/powerstate')
        except (HTTPError, URLError, ConnectionRefusedError):
            return False

        powerstate_soup = BeautifulSoup(powerstate_xml, 'html.parser')
        pwstate = powerstate_soup.e2instandby.renderContents().decode('UTF8')

        self._pwstate = ''

        if pwstate.find('false') >=0:
            self._pwstate = 'false'

        if pwstate.find('true') >=0:
            self._pwstate = 'true'

        if self._name == 'Enigma2 Satelite':
            about_xml = self.__requestCall('/web/about')
            about_soup = BeautifulSoup(about_xml, 'html.parser')
            name = about_soup.e2model.renderContents().decode('UTF8')
            if name:
                self._name = name

        if self._pwstate == 'false':
            subservices_xml = self.__requestCall('/web/subservices')
            subservices_soup = BeautifulSoup(subservices_xml, 'html.parser')
            servicename = subservices_soup.e2servicename.renderContents().decode('UTF8')
            service_reference = subservices_soup.e2servicereference.renderContents().decode('UTF8')

            eventtitle = 'N/A'
            if service_reference != 'N/A':
                epgservicenow_xml = self.__requestCall('/web/epgservicenow?sRef=' + service_reference)
                epgservicenow_soup = BeautifulSoup(epgservicenow_xml, 'html.parser')
                eventtitle = epgservicenow_soup.e2eventtitle.renderContents().decode('UTF8')

            vol_xml = self.__requestCall('/web/vol')
            vol_soup = BeautifulSoup(vol_xml, 'html.parser')
            volcurrent = vol_soup.e2current.renderContents().decode('UTF8')
            volmuted = vol_soup.e2ismuted.renderContents().decode('UTF8')

            self._volume = int(volcurrent) / MAX_VOLUME if volcurrent else None
            self._muted = (volmuted == 'True') if volmuted else None

            self._selected_source = (servicename + ' - ' + eventtitle)

        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._pwstate == 'true':
            return STATE_OFF
        if self._pwstate == 'false':
            return STATE_ON

        return STATE_UNKNOWN

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_ENIGMA

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._selected_source

    @property
    def source(self):
        """Return the current input source."""
        return self._selected_source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    def select_source(self, source):
        """Select input source."""
        try:
            self.__requestCall('/web/zap?sRef=' + self._sources[source])
        except (HTTPError, URLError, ConnectionRefusedError):
            return False

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        try:
            volset = str(round(volume * MAX_VOLUME))
            self.__requestCall('/web/vol?set=set' + volset)
        except (HTTPError, URLError, ConnectionRefusedError):
            return False

    def mute_volume(self, mute):
        """Mute or unmute media player."""
        try:
            self.__requestCall('/web/vol?set=mute')
        except (HTTPError, URLError, ConnectionRefusedError):
            return False

    def turn_on(self):
        """Turn the media player on."""
        try:
            self.__requestCall('/web/powerstate?newstate=4')
        except (HTTPError, URLError, ConnectionRefusedError):
            return False

    def turn_off(self):
        """Turn off media player."""
        try:
            self.__requestCall('/web/powerstate?newstate=5')
        except (HTTPError, URLError, ConnectionRefusedError):
            return False
