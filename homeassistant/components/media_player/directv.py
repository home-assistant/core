"""
Support for the DirecTV receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.directv/
"""
import asyncio
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
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from DirectPy import DIRECTV

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


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
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
            'entities': async_add_entities
        }

    elif discovery_info:
        host = discovery_info.get('host')
        name = 'DirecTV_{}'.format(discovery_info.get('serial', ''))

        if (host, DEFAULT_DEVICE) in known_devices:
            _LOGGER.debug("Discovered device on host %s is already"
                          " configured", host)
            return

#        from DirectPy import DIRECTV
        dtv = await hass.async_add_executor_job(
            DIRECTV, host, DEFAULT_PORT, DEFAULT_DEVICE)
        if dtv:
            try:
                resp = await hass.async_add_executor_job(
                    dtv.get_locations)
            except requests.exceptions.RequestException as ex:
                # Use uPnP data only
                _LOGGER.debug("Request exception %s trying to get "
                              "locations", ex)
                resp = {
                    'locations': [{
                        'locationName': name,
                        'clientAddr': DEFAULT_DEVICE
                    }]
                }
        else:
            resp = {
                'locations': [{
                    'locationName': name,
                    'clientAddr': DEFAULT_DEVICE
                }]
            }

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
            CONF_DISCOVER_CLIENTS: DEFAULT_DISCOVER_CLIENTS,
            CONF_CLIENT_DISCOVER_INTERVAL:
                DEFAULT_CLIENT_DISCOVER_INTERVAL,
            'entities': async_add_entities
        }

    if directv_entity is not None:
        hass.data.setdefault(DATA_DIRECTV, set()).add((
            directv_entity[CONF_HOST], directv_entity[CONF_DEVICE]))
        async_add_entities([DirecTvDevice(**directv_entity)])


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
        self._async_add_entities = kwargs.get('entities')

        self.dtv = None
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
            _LOGGER.debug("%s: Created entity DirecTV client %s",
                          self._name, self._device)
        else:
            _LOGGER.debug("%s: Created entity DirecTV device",
                          self._name)

    async def async_added_to_hass(self):
        """Connect to DVR instance."""
        await self._async_get_dtv_instance()

    async def _async_discover_directv_client_devices(self, now=None):
        """Discover new client devices connected to the main DVR."""
        known_devices = self.hass.data.get(DATA_DIRECTV, set())
        discovered_devices = []
        dtvs = []

        # Attempt to discover additional RVU units
        if now:
            _LOGGER.debug("%s: Scheduled discovery of DirecTV devices on %s",
                          self.entity_id, self._host)
        else:
            _LOGGER.debug("%s: Initial discovery of DirecTV devices on %s",
                          self.entity_id, self._host)

        _LOGGER.debug("%s: Current known devices: %s",
                      self.entity_id, known_devices)

        try:
            resp = await self._async_get_locations()
        except requests.exceptions.RequestException as ex:
            _LOGGER.debug("%s: Request exception %s trying to discover "
                          "new clients", self.entity_id, ex)

        for loc in resp.get('locations') or []:
            if 'locationName' not in loc or 'clientAddr' not in loc or\
               loc.get('clientAddr') == 0:
                continue

            # Make sure that this device is not already configured
            # Comparing based on host (IP) and clientAddr.
            if (self._host, loc['clientAddr']) in known_devices:
                _LOGGER.debug("%s: Discovered device %s on host %s with "
                              "client address %s is already "
                              "configured",
                              self.entity_id,
                              str.title(loc['locationName']),
                              self._host, loc['clientAddr'])
            else:
                _LOGGER.debug("%s: Adding discovered device %s with"
                              " client address %s",
                              self.entity_id,
                              str.title(loc['locationName']),
                              loc['clientAddr'])
                discovered_devices.append({
                    CONF_NAME: str.title(loc['locationName']),
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_DEVICE: loc['clientAddr'],
                    CONF_DISCOVER_CLIENTS: False,
                    'entities': self._async_add_entities
                })

        if discovered_devices:
            _LOGGER.debug("%s: Adding %s new DirecTV entities to HASS",
                          self.entity_id, len(discovered_devices))

            for new_device in discovered_devices:
                dtvs.append(DirecTvDevice(**new_device))
                self.hass.data.setdefault(DATA_DIRECTV, set()).add(
                    (new_device[CONF_HOST], new_device[CONF_DEVICE]))

            self._async_add_entities(dtvs)

    async def _async_get_dtv_instance(self):
        """Get the DTV instance to work with."""
        if self.dtv:
            return self.dtv

        try:
            self.dtv = await self.hass.async_add_executor_job(
                DIRECTV, self._host, self._port, self._device)
        except requests.exceptions.RequestException as ex:
            _LOGGER.warning("Exception trying to connect to DVR, will try "
                            "again later: %s", ex)
            self.dtv = None

        if self.dtv:
            _LOGGER.debug("%s: Successfull connection to DVR on %s",
                          self.entity_id, self._host)

            if self._discover_clients:
                # We are connected to DVR and will discover any potential
                # clients. Schedule discovery
                # Create a task to already do first discovery.
                self.hass.async_create_task(
                    self._async_discover_directv_client_devices()
                )

                # Schedule discovery to run based on interval.
                async_track_time_interval(
                    self.hass, self._async_discover_directv_client_devices,
                    self._client_discover_interval)
                _LOGGER.debug("%s: Client discovery scheduled for every %s",
                              self.entity_id, self._client_discover_interval)

        return self.dtv

    async def async_update(self):
        """Retrieve latest state."""
        _LOGGER.debug("%s: Updating status", self.entity_id)
        try:
            self._available = True
            self._is_standby = await self._async_get_standby()
            if self._is_standby:
                self._current = None
                self._is_recorded = None
                self._paused = None
                self._assumed_state = False
                self._last_position = None
                self._last_update = None
            else:
                self._current = await self._async_get_tuned()
                # If status is not 200 then try a second time.
                if self._current['status']['code'] != 200:
                    _LOGGER.debug("%s: Invalid status %s received, retrying.",
                                  self.entity_id,
                                  self._current['status']['code'])
                    # Wait for 1 second as most likely this is due to
                    # DVR just doing a change (i.e. channel, playing, ...)
                    await asyncio.sleep(1)
                    self._current = await self._async_get_tuned()

                if self._current['status']['code'] == 200:
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
                    _LOGGER.error("Invalid status %s received.",
                                  self._current['status']['code'])
                    self._available = False
        except requests.RequestException as ex:
            _LOGGER.error("Request error trying to update current status for"
                          " %s. %s", self._name, ex)
            self._available = False
        except Exception as ex:
            _LOGGER.error("Exception trying to update current status for"
                          " %s. %s", self._name, ex)
            self._available = False
            raise

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

    async def async_turn_on(self):
        """Turn on the receiver."""
        if self._is_client:
            raise NotImplementedError()

        _LOGGER.debug("%s: Turn on", self.entity_id)
        await self._async_key_press('poweron')

    async def async_turn_off(self):
        """Turn off the receiver."""
        if self._is_client:
            raise NotImplementedError()

        _LOGGER.debug("%s: Turn off", self.entity_id)
        await self._async_key_press('poweroff')

    async def async_media_play(self):
        """Send play command."""
        _LOGGER.debug("%s: Play", self.entity_id)
        await self._async_key_press('play')

    async def async_media_pause(self):
        """Send pause command."""
        _LOGGER.debug("%s: Pause", self.entity_id)
        await self._async_key_press('pause')

    async def async_media_stop(self):
        """Send stop command."""
        _LOGGER.debug("%s: Stop", self.entity_id)
        await self._async_key_press('stop')

    async def async_media_previous_track(self):
        """Send rewind command."""
        _LOGGER.debug("%s: Rewind", self.entity_id)
        await self._async_key_press('rew')

    async def async_media_next_track(self):
        """Send fast forward command."""
        _LOGGER.debug("%s: Fast forward", self.entity_id)
        await self._async_key_press('ffwd')

    def play_media(self, media_type, media_id, **kwargs):
        """Select input source."""
        if media_type != MEDIA_TYPE_CHANNEL:
            _LOGGER.error("Invalid media type %s. Only %s is supported",
                          media_type, MEDIA_TYPE_CHANNEL)
            raise NotImplementedError()

            return

        _LOGGER.debug("Changing channel on %s to %s", self._name, media_id)
        self.dtv.tune_channel(media_id)
