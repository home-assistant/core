"""Support for interface with a Bravia TV."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    DEVICE_CLASS_TV,
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PIN, STATE_OFF, STATE_ON
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json

from .const import (
    ATTR_MANUFACTURER,
    BRAVIA_CONFIG_FILE,
    CLIENTID_PREFIX,
    CONF_IGNORED_SOURCES,
    DEFAULT_NAME,
    DOMAIN,
    NICKNAME,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_BRAVIA = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY
    | SUPPORT_STOP
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Bravia TV platform."""
    host = config[CONF_HOST]

    bravia_config_file_path = hass.config.path(BRAVIA_CONFIG_FILE)
    bravia_config = await hass.async_add_executor_job(
        load_json, bravia_config_file_path
    )
    if not bravia_config:
        _LOGGER.error(
            "Configuration import failed, there is no bravia.conf file in the configuration folder"
        )
        return

    while bravia_config:
        # Import a configured TV
        host_ip, host_config = bravia_config.popitem()
        if host_ip == host:
            pin = host_config[CONF_PIN]

            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={CONF_HOST: host, CONF_PIN: pin},
                )
            )
            return


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add BraviaTV entities from a config_entry."""
    ignored_sources = []
    pin = config_entry.data[CONF_PIN]
    unique_id = config_entry.unique_id
    device_info = {
        "identifiers": {(DOMAIN, unique_id)},
        "name": DEFAULT_NAME,
        "manufacturer": ATTR_MANUFACTURER,
        "model": config_entry.title,
    }

    braviarc = hass.data[DOMAIN][config_entry.entry_id]

    ignored_sources = config_entry.options.get(CONF_IGNORED_SOURCES, [])

    async_add_entities(
        [
            BraviaTVDevice(
                braviarc, DEFAULT_NAME, pin, unique_id, device_info, ignored_sources
            )
        ]
    )


class BraviaTVDevice(MediaPlayerEntity):
    """Representation of a Bravia TV."""

    def __init__(self, client, name, pin, unique_id, device_info, ignored_sources):
        """Initialize the Bravia TV device."""

        self._pin = pin
        self._braviarc = client
        self._name = name
        self._state = STATE_OFF
        self._muted = False
        self._program_name = None
        self._channel_name = None
        self._channel_number = None
        self._source = None
        self._source_list = []
        self._original_content_list = []
        self._content_mapping = {}
        self._duration = None
        self._content_uri = None
        self._playing = False
        self._start_date_time = None
        self._program_media_type = None
        self._min_volume = None
        self._max_volume = None
        self._volume = None
        self._unique_id = unique_id
        self._device_info = device_info
        self._ignored_sources = ignored_sources
        self._state_lock = asyncio.Lock()
        self._need_refresh = True

    async def async_update(self):
        """Update TV info."""
        if self._state_lock.locked():
            return

        if self._state == STATE_OFF:
            self._need_refresh = True

        power_status = await self.hass.async_add_executor_job(
            self._braviarc.get_power_status
        )
        if power_status == "active":
            if self._need_refresh:
                connected = await self.hass.async_add_executor_job(
                    self._braviarc.connect, self._pin, CLIENTID_PREFIX, NICKNAME
                )
                self._need_refresh = False
            else:
                connected = self._braviarc.is_connected()
            if not connected:
                return

            self._state = STATE_ON
            if (
                await self._async_refresh_volume()
                and await self._async_refresh_channels()
            ):
                await self._async_refresh_playing_info()
                return
        self._state = STATE_OFF

    def _get_source(self):
        """Return the name of the source."""
        for key, value in self._content_mapping.items():
            if value == self._content_uri:
                return key

    async def _async_refresh_volume(self):
        """Refresh volume information."""
        volume_info = await self.hass.async_add_executor_job(
            self._braviarc.get_volume_info
        )
        if volume_info is not None:
            self._volume = volume_info.get("volume")
            self._min_volume = volume_info.get("minVolume")
            self._max_volume = volume_info.get("maxVolume")
            self._muted = volume_info.get("mute")
            return True
        return False

    async def _async_refresh_channels(self):
        """Refresh source and channels list."""
        if not self._source_list:
            self._content_mapping = await self.hass.async_add_executor_job(
                self._braviarc.load_source_list
            )
            self._source_list = []
            if not self._content_mapping:
                return False
            for key in self._content_mapping:
                if key not in self._ignored_sources:
                    self._source_list.append(key)
        return True

    async def _async_refresh_playing_info(self):
        """Refresh Playing information."""
        playing_info = await self.hass.async_add_executor_job(
            self._braviarc.get_playing_info
        )
        self._program_name = playing_info.get("programTitle")
        self._channel_name = playing_info.get("title")
        self._program_media_type = playing_info.get("programMediaType")
        self._channel_number = playing_info.get("dispNum")
        self._content_uri = playing_info.get("uri")
        self._source = self._get_source()
        self._duration = playing_info.get("durationSec")
        self._start_date_time = playing_info.get("startDateTime")
        if not playing_info:
            self._channel_name = "App"

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_class(self):
        """Set the device class to TV."""
        return DEVICE_CLASS_TV

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return self._device_info

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._volume is not None:
            return self._volume / 100
        return None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_BRAVIA

    @property
    def media_title(self):
        """Title of current playing media."""
        return_value = None
        if self._channel_name is not None:
            return_value = self._channel_name
            if self._program_name is not None:
                return_value = f"{return_value}: {self._program_name}"
        return return_value

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._channel_name

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._duration

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._braviarc.set_volume_level(volume)

    async def async_turn_on(self):
        """Turn the media player on."""
        async with self._state_lock:
            await self.hass.async_add_executor_job(self._braviarc.turn_on)

    async def async_turn_off(self):
        """Turn off media player."""
        async with self._state_lock:
            await self.hass.async_add_executor_job(self._braviarc.turn_off)

    def volume_up(self):
        """Volume up the media player."""
        self._braviarc.volume_up()

    def volume_down(self):
        """Volume down media player."""
        self._braviarc.volume_down()

    def mute_volume(self, mute):
        """Send mute command."""
        self._braviarc.mute_volume(mute)

    def select_source(self, source):
        """Set the input source."""
        if source in self._content_mapping:
            uri = self._content_mapping[source]
            self._braviarc.play_content(uri)

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._playing = True
        self._braviarc.media_play()

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self._braviarc.media_pause()

    def media_stop(self):
        """Send media stop command to media player."""
        self._playing = False
        self._braviarc.media_stop()

    def media_next_track(self):
        """Send next track command."""
        self._braviarc.media_next_track()

    def media_previous_track(self):
        """Send the previous track command."""
        self._braviarc.media_previous_track()
