"""
Support for the DirecTV receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.directv/
"""
import logging
from datetime import timedelta
import requests
import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_CHANNEL, MEDIA_TYPE_MOVIE, MEDIA_TYPE_TVSHOW, PLATFORM_SCHEMA,
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    MediaPlayerDevice)
from homeassistant.const import (
    CONF_DEVICE, CONF_HOST, CONF_NAME, CONF_PORT, STATE_OFF, STATE_PAUSED,
    STATE_PLAYING)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['directpy==0.5']

_LOGGER = logging.getLogger(__name__)

ATTR_MEDIA_CURRENTLY_RECORDING = 'media_currently_recording'
ATTR_MEDIA_RATING = 'media_rating'
ATTR_MEDIA_RECORDED = 'media_recorded'
ATTR_MEDIA_START_TIME = 'media_start_time'

CONF_DISCOVER_CLIENTS = 'discover_clients'
CONF_CLIENT_DISCOVER_INTERVAL = 'client_discover_interval'

DEFAULT_DEVICE = '0'
DEFAULT_DISCOVER_CLIENTS = True
DEFAULT_NAME = "DirecTV Receiver"
DEFAULT_PORT = 8080
DEFAULT_CLIENT_DISCOVER_INTERVAL = timedelta(seconds=300)

SUPPORT_DTV = SUPPORT_PAUSE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
    SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_NEXT_TRACK | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY

SUPPORT_DTV_CLIENT = SUPPORT_PAUSE | \
    SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_NEXT_TRACK | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY

SUPPORT_DTV_CLIENT = SUPPORT_PAUSE | \
    SUPPORT_PLAY_MEDIA | SUPPORT_SELECT_SOURCE | SUPPORT_STOP | \
    SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY

DATA_DIRECTV = 'data_directv'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
    vol.Optional(CONF_DISCOVER_CLIENTS, default=DEFAULT_DISCOVER_CLIENTS):
        cv.boolean,
    vol.Optional(CONF_CLIENT_DISCOVER_INTERVAL,
                 default=DEFAULT_CLIENT_DISCOVER_INTERVAL):
        cv.time_period,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the DirecTV platform."""
    known_devices = hass.data.get(DATA_DIRECTV, set())
    directv_entity = None

    if CONF_HOST in config:
        _LOGGER.debug("Adding configured device %s with client address %s ",
                      config.get(CONF_NAME), config.get(CONF_DEVICE))
        directv_entity = {
            CONF_NAME: config.get(CONF_NAME),
            CONF_HOST: config.get(CONF_HOST),
            CONF_PORT: config.get(CONF_PORT),
            CONF_DEVICE: config.get(CONF_DEVICE),
            CONF_DISCOVER_CLIENTS: config.get(CONF_DISCOVER_CLIENTS),
            CONF_CLIENT_DISCOVER_INTERVAL: config.get(
                CONF_CLIENT_DISCOVER_INTERVAL),
            'entities': add_entities
        }

    elif discovery_info:
        host = discovery_info.get('host')
        if (host, DEFAULT_DEVICE) in known_devices:
            name = 'DirecTV_{}'.format(discovery_info.get('serial', ''))
            _LOGGER.debug("Discovered device %s on host %s is already"
                          " configured", name, host)
        else:
            _LOGGER.debug("Adding discovered device %s on host %s",
                          name, host)
            directv_entity = {
                CONF_NAME: name,
                CONF_HOST: host,
                CONF_PORT: DEFAULT_PORT,
                CONF_DEVICE: '0',
                CONF_DISCOVER_CLIENTS: DEFAULT_DISCOVER_CLIENTS,
                CONF_CLIENT_DISCOVER_INTERVAL:
                    DEFAULT_CLIENT_DISCOVER_INTERVAL,
                'entities': add_entities
            }

    if directv_entity is not None:
        hass.data.setdefault(DATA_DIRECTV, set()).add((
            directv_entity[CONF_HOST], directv_entity[CONF_DEVICE]))
        add_entities([DirecTvDevice(**directv_entity)])


class DirecTvDevice(MediaPlayerDevice):
    """Representation of a DirecTV receiver on the network."""

    def __init__(self, **kwargs):
        """Initialize the device."""
        self._host = kwargs.get(CONF_HOST)
        self._name = kwargs.get(CONF_NAME, self._host)
        self._port = kwargs.get(CONF_PORT, DEFAULT_PORT)
        self._device = kwargs.get(CONF_DEVICE, DEFAULT_DEVICE)

        # This is a client device is client address is not 0
        self._is_client = self._device != DEFAULT_DEVICE
        # Disable discover_clients if this is a client device, otherwise
        # base it on configuration provided or default.
        self._discover_clients = kwargs.get(CONF_DISCOVER_CLIENTS,
                                            DEFAULT_DISCOVER_CLIENTS) \
            if not self._is_client else False
        self._client_discover_interval = kwargs.get(
            CONF_CLIENT_DISCOVER_INTERVAL, DEFAULT_CLIENT_DISCOVER_INTERVAL)
        self._add_entities = kwargs.get('entities')

        from DirectPy import DIRECTV
        self.dtv = DIRECTV(self._host, self._port, self._device)

        self._is_standby = True
        self._current = None
        self._last_update = None
        self._paused = None
        self._last_position = None
        self._is_recorded = None
        self._assumed_state = None
        self._available = False
        self._next_client_discover = dt_util.utcnow()

        if self._is_client:
            _LOGGER.debug("Created entity %s for DirecTV client %s",
                          self._name, self._device)
        else:
            _LOGGER.debug("Created entity %s for DirecTV device", self._name)
            if self._discover_clients:
                _LOGGER.debug("Will perform client discovery every %s",
                              self._client_discover_interval)

    def _discover_directv_client_devices(self):
        """Discover any client devices on the main DVR."""
        known_devices = self.hass.data.get(DATA_DIRECTV, set())
        discovered_devices = []

        # Attempt to discover additional RVU units
        _LOGGER.debug("Doing discovery of DirecTV devices on %s", self._host)

        resp = self.dtv.get_locations()

        _LOGGER.debug("Known devices: %s", known_devices)
        for loc in resp.get('locations') or []:
            if 'locationName' not in loc or 'clientAddr' not in loc or\
               loc.get('clientAddr') == 0:
                continue

            # Make sure that this device is not already configured
            # Comparing based on host (IP) and clientAddr.
            if (self._host, loc['clientAddr']) in known_devices:
                _LOGGER.debug("Discovered device %s on host %s with "
                              "client address %s is already "
                              "configured",
                              str.title(loc['locationName']),
                              self._host, loc['clientAddr'])
            else:
                _LOGGER.debug("Adding discovered device %s with"
                              " client address %s",
                              str.title(loc['locationName']),
                              loc['clientAddr'])
                discovered_devices.append({
                    CONF_NAME: str.title(loc['locationName']),
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_DEVICE: loc['clientAddr'],
                    CONF_DISCOVER_CLIENTS: False,
                    'entities': self._add_entities
                })

        return discovered_devices

    def _add_directv_entities(self, new_entities):
        """Add DirecTV client devices as entities in HASS."""
        dtvs = []

        if not new_entities:
            _LOGGER.debug("Adding %s new DirecTV entities to HASS",
                          len(new_entities))

            for new_entity in new_entities:
                dtvs.append(DirecTvDevice(**new_entity))
                self.hass.data.setdefault(DATA_DIRECTV, set()).add(
                    (new_entity[CONF_HOST], new_entity[CONF_DEVICE]))

            self._add_entities(dtvs)

    def update(self):
        """Retrieve latest state."""
        _LOGGER.debug("Updating status for %s", self._name)
        try:
            self._available = True
            self._is_standby = self.dtv.get_standby()
            if self._is_standby:
                self._current = None
                self._is_recorded = None
                self._paused = None
                self._assumed_state = False
                self._last_position = None
                self._last_update = None
            else:
                self._current = self.dtv.get_tuned()
                if self._current['status']['code'] == 200:
                    self._is_recorded = self._current.get('uniqueId')\
                        is not None
                    self._paused = self._last_position == \
                        self._current['offset']
                    self._assumed_state = self._is_recorded
                    self._last_position = self._current['offset']
                    self._last_update = dt_util.utcnow() if not self._paused \
                        or self._last_update is None else self._last_update
                else:
                    self._available = False
        except requests.RequestException as ex:
            _LOGGER.error("Request error trying to update current status for"
                          " %s. %s", self._name, ex)
            self._available = False
        except Exception:
            self._available = False
            raise

        # Perform discovery to determine if any new client devices have
        # shown up if client discovery is enabled (default) and defined time
        # has been elapsed since last discovery (default 5 minutes)
        if self._discover_clients and \
           dt_util.utcnow() >= self._next_client_discover:
            self._next_client_discover = dt_util.utcnow() +\
                self._client_discover_interval

            new_clients = []
            try:
                new_clients = self._discover_directv_client_devices()
            except requests.exceptions.RequestException as ex:
                _LOGGER.debug("Request exception %s trying to discover "
                              "new clients", ex)

            # If _add_entities is not defined but clients were found then
            # raise NotImplementedError.
            if self._add_entities is None and new_clients:
                raise NotImplementedError()
            else:
                self._add_directv_entities(new_clients)

            _LOGGER.debug("Next client discovery will occur on %s",
                          dt_util.as_local(self._next_client_discover))

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attributes = {}
        if not self._is_standby:
            attributes[ATTR_MEDIA_CURRENTLY_RECORDING] =\
                self.media_currently_recording
            attributes[ATTR_MEDIA_RATING] = self.media_rating
            attributes[ATTR_MEDIA_RECORDED] = self.media_recorded
            attributes[ATTR_MEDIA_START_TIME] = self.media_start_time

        return attributes

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    # MediaPlayerDevice properties and methods
    @property
    def state(self):
        """Return the state of the device."""
        if self._is_standby:
            return STATE_OFF

        # For recorded media we can determine if it is paused or not.
        # For live media we're unable to determine and will always return
        # playing instead.
        if self._paused:
            return STATE_PAUSED

        return STATE_PLAYING

    @property
    def available(self):
        """Return if able to retrieve information from DVR or not."""
        return self._available

    @property
    def assumed_state(self):
        """Return if we assume the state or not."""
        return self._assumed_state

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        if self._is_standby:
            return None

        return self._current['programId']

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        if self._is_standby:
            return None

        if 'episodeTitle' in self._current:
            return MEDIA_TYPE_TVSHOW

        return MEDIA_TYPE_MOVIE

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        if self._is_standby:
            return None

        return self._current['duration']

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self._is_standby:
            return None

        return self._last_position

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        if self._is_standby:
            return None

        return self._last_update

    @property
    def media_title(self):
        """Return the title of current playing media."""
        if self._is_standby:
            return None

        return self._current['title']

    @property
    def media_series_title(self):
        """Return the title of current episode of TV show."""
        if self._is_standby:
            return None

        return self._current.get('episodeTitle')

    @property
    def media_channel(self):
        """Return the channel current playing media."""
        if self._is_standby:
            return None

        return "{} ({})".format(
            self._current['callsign'], self._current['major'])

    @property
    def source(self):
        """Name of the current input source."""
        if self._is_standby:
            return None

        return self._current['major']

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_DTV_CLIENT if self._is_client else SUPPORT_DTV

    @property
    def media_currently_recording(self):
        """If the media is currently being recorded or not."""
        if self._is_standby:
            return None

        return self._current['isRecording']

    @property
    def media_rating(self):
        """TV Rating of the current playing media."""
        if self._is_standby:
            return None

        return self._current['rating']

    @property
    def media_recorded(self):
        """If the media was recorded or live."""
        if self._is_standby:
            return None

        return self._is_recorded

    @property
    def media_start_time(self):
        """Start time the program aired."""
        if self._is_standby:
            return None

        return dt_util.as_local(
            dt_util.utc_from_timestamp(self._current['startTime']))

    def turn_on(self):
        """Turn on the receiver."""
        if self._is_client:
            raise NotImplementedError()

        _LOGGER.debug("Turn on %s", self._name)
        self.dtv.key_press('poweron')

    def turn_off(self):
        """Turn off the receiver."""
        if self._is_client:
            raise NotImplementedError()

        _LOGGER.debug("Turn off %s", self._name)
        self.dtv.key_press('poweroff')

    def media_play(self):
        """Send play command."""
        _LOGGER.debug("Play on %s", self._name)
        self.dtv.key_press('play')

    def media_pause(self):
        """Send pause command."""
        _LOGGER.debug("Pause on %s", self._name)
        self.dtv.key_press('pause')

    def media_stop(self):
        """Send stop command."""
        _LOGGER.debug("Stop on %s", self._name)
        self.dtv.key_press('stop')

    def media_previous_track(self):
        """Send rewind command."""
        _LOGGER.debug("Rewind on %s", self._name)
        self.dtv.key_press('rew')

    def media_next_track(self):
        """Send fast forward command."""
        _LOGGER.debug("Fast forward on %s", self._name)
        self.dtv.key_press('ffwd')

    def play_media(self, media_type, media_id, **kwargs):
        """Select input source."""
        if media_type != MEDIA_TYPE_CHANNEL:
            _LOGGER.error("Invalid media type %s. Only %s is supported",
                          media_type, MEDIA_TYPE_CHANNEL)
            return

        _LOGGER.debug("Changing channel on %s to %s", self._name, media_id)
        self.dtv.tune_channel(media_id)
