"""
Support for the DirecTV receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.directv/
"""
import logging
from datetime import timedelta
from functools import partial
import requests
import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_CHANNEL, MEDIA_TYPE_MOVIE, MEDIA_TYPE_TVSHOW, PLATFORM_SCHEMA,
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    MediaPlayerDevice)
from homeassistant.const import (
    CONF_DEVICE, CONF_HOST, CONF_NAME, CONF_PORT, EVENT_HOMEASSISTANT_START,
    STATE_OFF, STATE_PAUSED, STATE_PLAYING)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_time_interval
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['directpy==0.6']

_LOGGER = logging.getLogger(__name__)

ATTR_MEDIA_CURRENTLY_RECORDING = 'media_currently_recording'
ATTR_MEDIA_RATING = 'media_rating'
ATTR_MEDIA_RECORDED = 'media_recorded'
ATTR_MEDIA_START_TIME = 'media_start_time'

DEFAULT_DEVICE = '0'
DEFAULT_NAME = "DirecTV Receiver"
DEFAULT_PORT = 8080
DEFAULT_CLIENT_DISCOVER_INTERVAL = timedelta(seconds=300)

RECEIVER_ID = 'receiver_id'
SUPPORT_DTV = SUPPORT_PAUSE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
    SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_NEXT_TRACK | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY

SUPPORT_DTV_CLIENT = SUPPORT_PAUSE | \
    SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_NEXT_TRACK | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY

DATA_DIRECTV = 'data_directv'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the DirecTV platform."""
    known_devices = hass.data.get(DATA_DIRECTV, set())
    directv_entity = None

    if CONF_HOST in config:
        discovered = False
        name = config.get(CONF_NAME)
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
        device = config.get(CONF_DEVICE)
        _LOGGER.debug("Adding configured device %s with client address %s ",
                      name, device)

        resp = {}
        from DirectPy import DIRECTV
        try:
            dtv = DIRECTV(host, port, device)
            resp = dtv.get_version()
        except requests.exceptions.RequestException as ex:
            # Use uPnP data only
            _LOGGER.debug("Request exception %s trying to get "
                          "receiver id for %s", ex, name)
            resp = {}

        directv_entity = {
            CONF_NAME: name,
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_DEVICE: device,
            RECEIVER_ID: resp.get('receiverId', host).replace(' ', ''),
        }

    elif discovery_info:
        discovered = True
        host = discovery_info.get('host')
        receiver_id = discovery_info.get('serial', '').split('-')[-1]
        receiver_id = receiver_id if receiver_id else host
        name = host

        if (receiver_id, DEFAULT_DEVICE) in known_devices:
            _LOGGER.debug("Discovered device on host %s is already"
                          " configured", host)
            return

        resp = {}
        from DirectPy import DIRECTV
        try:
            dtv = DIRECTV(host, DEFAULT_PORT, DEFAULT_DEVICE)
            resp = dtv.get_locations()
        except requests.exceptions.RequestException as ex:
            _LOGGER.debug("Request exception %s trying to retrieve "
                          "name for %s", ex, name)
            resp = {}

        for loc in resp.get("locations") or []:
            if loc.get("clientAddr") == DEFAULT_DEVICE and \
               "locationName" in loc:
                name = str.title(loc["locationName"])
                break

        _LOGGER.debug("Adding discovered device %s on host %s",
                      name, host)
        directv_entity = {
            CONF_NAME: name,
            CONF_HOST: host,
            CONF_PORT: DEFAULT_PORT,
            CONF_DEVICE: DEFAULT_DEVICE,
            RECEIVER_ID: receiver_id,
        }

    if directv_entity is None:
        return

    # Add entries for both as host and receiver id
    hass.data.setdefault(DATA_DIRECTV, set()).add((
        directv_entity[CONF_HOST], directv_entity[CONF_DEVICE]))

    hass.data[DATA_DIRECTV].add((
        directv_entity[RECEIVER_ID], directv_entity[CONF_DEVICE]))

    add_entities([DirecTvDevice(
        directv_entity[CONF_NAME], directv_entity[CONF_HOST],
        directv_entity[CONF_PORT], directv_entity[CONF_DEVICE])])

    # Enable client discovery.
    DirecTvClientDiscovery(
        hass, add_entities, discovered,
        directv_entity[CONF_HOST], directv_entity[CONF_NAME],
        directv_entity[RECEIVER_ID], directv_entity[CONF_PORT],
    )


class DirecTvClientDiscovery:
    """Discover client devices attached to DVR."""

    def __init__(self, hass, add_entities, discovered, host, name,
                 receiver_id, port=DEFAULT_PORT):
        """Initialize discovery for client devices."""
        self._hass = hass
        self._add_entities = add_entities
        self._discovered = discovered
        self._host = host
        self._name = name if name else host
        self._port = port
        self._receiver_id = receiver_id if receiver_id != host else None

        self.dtv = None

        # Client discovery to be started once HASS is started to ensure
        # all configured devices have been added first.
        def client_discovery_startup(event):
            # Perform a discovery if the main entity was discovered as well or
            # HASS started.
            if self._discovered or event:
                self._discover_directv_client_devices()

            # Schedule discovery to run based on interval.
            track_time_interval(
                self._hass, self._discover_directv_client_devices,
                DEFAULT_CLIENT_DISCOVER_INTERVAL)
            _LOGGER.debug("%s: Client discovery scheduled for every %s",
                          self._name, DEFAULT_CLIENT_DISCOVER_INTERVAL)

        # If HASS is already running then start the discovery.
        # If HASS is not yet running, register for the event before starting
        # the discovery.
        if self._hass.is_running:
            client_discovery_startup(None)
        else:
            self._hass.bus.listen_once(
                EVENT_HOMEASSISTANT_START, client_discovery_startup)

    def _discover_directv_client_devices(self, now=None):
        """Discover new client devices connected to the main DVR."""
        known_devices = self._hass.data.get(DATA_DIRECTV)
        discovered_devices = []
        dtvs = []

        # Attempt to discover additional RVU units
        if now:
            _LOGGER.debug("%s: Scheduled discovery of DirecTV devices on %s",
                          self._name, self._host)
        else:
            _LOGGER.debug("%s: Initial discovery of DirecTV devices on %s",
                          self._name, self._host)

        _LOGGER.debug("%s: Current known devices: %s",
                      self._name, known_devices)

        if not self.dtv:
            from DirectPy import DIRECTV
            try:
                self.dtv = DIRECTV(self._host, self._port, DEFAULT_DEVICE)
            except requests.exceptions.RequestException as ex:
                # Use uPnP data only
                _LOGGER.debug("%s: Request exception %s trying to get "
                              "locations", self._name, ex)
                self.dtv = None

        if not self.dtv:
            return

        # If for some reason we did not have a receiver id then retrieve
        # it now.
        if not self._receiver_id:
            receiver_id_resp = None
            try:
                receiver_id_resp = self.dtv.get_version()
            except requests.exceptions.RequestException as ex:
                _LOGGER.debug("Request exception %s trying to get "
                              "receiver id for %s", ex, self._name)
                receiver_id_resp = None

            if not receiver_id_resp:
                self._receiver_id = receiver_id_resp.get('receiverId')

            # Add the receiver ID to HASS data to prevent duplicate
            # discovery, do this for all entities with same hostname
            if not self._receiver_id:
                add_set = set()
                for device in known_devices:
                    if device[0] == self._host:
                        add_set.add((self._receiver_id, device[1]))

                self._hass.data['DATA_DIRECTV'].update(add_set)

        # Get all the devices connected to the main DVR
        try:
            resp = self.dtv.get_locations()
        except requests.exceptions.RequestException as ex:
            # Use uPnP data only
            _LOGGER.debug("%s: Request exception %s trying to get "
                          "locations", self._name, ex)
            resp = None

        if not resp:
            return

        receiver_id = self._receiver_id if self._receiver_id else self._host
        for loc in resp.get('locations') or []:
            if 'locationName' not in loc or 'clientAddr' not in loc or\
               loc.get('clientAddr') == DEFAULT_DEVICE:
                continue

            # Make sure that this device is not already configured
            # Comparison is based on receiver ID if known, otherwise
            # it will be based on host
            if (receiver_id, loc['clientAddr']) in known_devices:
                _LOGGER.debug("%s: Discovered device %s on host %s with "
                              "client address %s is already "
                              "configured",
                              self._name,
                              str.title(loc['locationName']),
                              self._host, loc['clientAddr'])
            else:
                _LOGGER.debug("%s: Adding discovered device %s with"
                              " client address %s",
                              self._name,
                              str.title(loc['locationName']),
                              loc['clientAddr'])
                discovered_devices.append({
                    CONF_NAME: str.title(loc['locationName']),
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_DEVICE: loc['clientAddr']
                })

        if discovered_devices:
            _LOGGER.debug("%s: Adding %s new DirecTV entities to HASS",
                          self._name, len(discovered_devices))

            for new_device in discovered_devices:
                dtvs.append(DirecTvDevice(
                    new_device[CONF_NAME], new_device[CONF_HOST],
                    new_device[CONF_PORT], new_device[CONF_DEVICE]))

                self._hass.data.setdefault(DATA_DIRECTV, set()).add(
                    (self._receiver_id, new_device[CONF_DEVICE]))

            self._add_entities(dtvs)


class DirecTvDevice(MediaPlayerDevice):
    """Representation of a DirecTV receiver on the network."""

    def __init__(self, name, host, port, device):
        """Initialize the device."""
        self._name = name
        self._host = host
        self._port = port
        self._device = device

        # This is a client device is client address is not 0
        self._is_client = self._device != DEFAULT_DEVICE
        self.dtv = None
        self._is_standby = True
        self._current = None
        self._last_update = None
        self._paused = None
        self._last_position = None
        self._is_recorded = None
        self._assumed_state = None
        self._available = False
        self._first_error_timestamp = None

    async def async_added_to_hass(self):
        """Connect to DVR instance."""
        if self._is_client:
            _LOGGER.debug("%s: Created entity DirecTV client %s",
                          self.entity_id, self._device)
        else:
            _LOGGER.debug("%s: Created entity DirecTV device",
                          self.entity_id)

        await self.hass.async_add_executor_job(self.get_dtv_instance)

    def update(self):
        """Retrieve latest state."""
        _LOGGER.debug("%s: Updating status", self.entity_id)
        try:
            self._available = True
            self._is_standby = self.call_api(None, 'get_standby')
            if self._is_standby or self._is_standby is None:
                self._current = None
                self._is_recorded = None
                self._paused = None
                self._assumed_state = False
                self._last_position = None
                self._last_update = None
                if self._is_standby is None:
                    self._available = False
            else:
                self._current = self.call_api(None, 'get_tuned')
                if self._current['status']['code'] == 200:
                    self._first_error_timestamp = None
                    self._is_recorded = self._current.get('uniqueId')\
                        is not None
                    self._paused = self._last_position == \
                        self._current['offset']
                    # Assumed state of playing if offset is changing and
                    # it is greater then duration.
                    self._assumed_state = self._current['offset'] > \
                        self._current['duration'] and not self._paused
                    self._last_position = self._current['offset']
                    self._last_update = dt_util.utcnow() if not self._paused \
                        or self._last_update is None else self._last_update
                else:
                    # If an error is received then only set to unavailable if
                    # this started at least 1 minute ago.
                    log_message = "{}: Invalid status {} received".format(
                        self.entity_id,
                        self._current['status']['code']
                    )
                    if self._check_state_available():
                        _LOGGER.debug(log_message)
                    else:
                        _LOGGER.error(log_message)

        except requests.RequestException as ex:
            _LOGGER.error("%s: Request error trying to update current status: "
                          "%s", self.entity_id, ex)
            self._check_state_available()

        except Exception as ex:
            _LOGGER.error("%s: Exception trying to update current status: %s",
                          self.entity_id, ex)
            self._available = False
            if not self._first_error_timestamp:
                self._first_error_timestamp = dt_util.utcnow()
            raise

    def _check_state_available(self):
        """Set to unavailable if issue been occurring over 1 minute."""
        if not self._first_error_timestamp:
            self._first_error_timestamp = dt_util.utcnow()
        else:
            tdelta = dt_util.utcnow() - self._first_error_timestamp
            if tdelta.total_seconds() >= 60:
                self._available = False

        return self._available

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

        return STATE_PAUSED if self._paused else STATE_PLAYING

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

        _LOGGER.debug("%s: Turn on", self.entity_id)
        self.key_press('poweron')

    def turn_off(self):
        """Turn off the receiver."""
        if self._is_client:
            raise NotImplementedError()

        _LOGGER.debug("%s: Turn off", self.entity_id)
        self.key_press('poweroff')

    def media_play(self):
        """Send play command."""
        _LOGGER.debug("%s: Play", self.entity_id)
        self.key_press('play')

    def media_pause(self):
        """Send pause command."""
        _LOGGER.debug("%s: Pause", self.entity_id)
        self.key_press('pause')

    def media_stop(self):
        """Send stop command."""
        _LOGGER.debug("%s: Stop", self.entity_id)
        self.key_press('stop')

    def media_previous_track(self):
        """Send rewind command."""
        _LOGGER.debug("%s: Rewind", self.entity_id)
        self.key_press('rew')

    def media_next_track(self):
        """Send fast forward command."""
        _LOGGER.debug("%s: Fast forward", self.entity_id)
        self.key_press('ffwd')

    def play_media(self, media_type, media_id, **kwargs):
        """Select input source."""
        if media_type != MEDIA_TYPE_CHANNEL:
            _LOGGER.error("%s: Invalid media type %s. Only %s is supported",
                          self.entity_id, media_type, MEDIA_TYPE_CHANNEL)
            raise NotImplementedError()

        _LOGGER.debug("%s: Changing channel to %s", self.entity_id, media_id)
        try:
            self.call_api("Not yet connected to DVR",
                          'tune_channel', media_id)
        except requests.RequestException as ex:
            _LOGGER.error("%s: Request error trying to change channel: %s",
                          self.entity_id, ex)

    def get_dtv_instance(self):
        """Get the DTV instance to work with."""
        if self.dtv:
            return self.dtv

        from DirectPy import DIRECTV
        try:
            self.dtv = DIRECTV(self._host, self._port, self._device)
        except requests.exceptions.RequestException as ex:
            _LOGGER.warning("%s: Exception trying to connect to DVR, will try "
                            "again later: %s", self.entity_id, ex)
            self.dtv = None

        if not self.dtv:
            return

        _LOGGER.debug("%s: Successfully connected to %s",
                      self.entity_id, self._host)
        return self.dtv

    def call_api(self, not_connected_error, api_call, *args, **kwargs):
        """Call API method of DirecTV class."""
        if not self.get_dtv_instance():
            if not_connected_error:
                _LOGGER.error("%s: Not yet connected to DVR", self.entity_id)
            else:
                _LOGGER.debug("%s: No connection to DVR", self.entity_id)
            return

        _LOGGER.debug("%s: Executing API call: %s", self.entity_id, api_call)
        return partial(getattr(self.dtv, api_call), *args, **kwargs)()

    def key_press(self, key):
        """Call sync function for key_press."""
        try:
            return self.call_api("Not yet connected to DVR", 'key_press', key)

        except requests.RequestException as ex:
            _LOGGER.error("%s: Request error trying to send key press: %s",
                          self.entity_id, ex)
            return
