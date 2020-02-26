"""Platform for the KEF Wireless Speakers."""

from datetime import timedelta
from functools import partial
import ipaddress
import logging

from aiokef import AsyncKefSpeaker
from getmac import get_mac_address
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
    MediaPlayerDevice,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "KEF"
DEFAULT_PORT = 50001
DEFAULT_MAX_VOLUME = 0.5
DEFAULT_VOLUME_STEP = 0.05
DEFAULT_INVERSE_SPEAKER_MODE = False
DEFAULT_SUPPORTS_ON = True

DOMAIN = "kef"

SCAN_INTERVAL = timedelta(seconds=30)

SOURCES = {"LSX": ["Wifi", "Bluetooth", "Aux", "Opt"]}
SOURCES["LS50"] = SOURCES["LSX"] + ["Usb"]

CONF_MAX_VOLUME = "maximum_volume"
CONF_VOLUME_STEP = "volume_step"
CONF_INVERSE_SPEAKER_MODE = "inverse_speaker_mode"
CONF_SUPPORTS_ON = "supports_on"
CONF_STANDBY_TIME = "standby_time"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TYPE): vol.In(["LS50", "LSX"]),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MAX_VOLUME, default=DEFAULT_MAX_VOLUME): cv.small_float,
        vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP): cv.small_float,
        vol.Optional(
            CONF_INVERSE_SPEAKER_MODE, default=DEFAULT_INVERSE_SPEAKER_MODE
        ): cv.boolean,
        vol.Optional(CONF_SUPPORTS_ON, default=DEFAULT_SUPPORTS_ON): cv.boolean,
        vol.Optional(CONF_STANDBY_TIME): vol.In([20, 60]),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the KEF platform."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    host = config[CONF_HOST]
    speaker_type = config[CONF_TYPE]
    port = config[CONF_PORT]
    name = config[CONF_NAME]
    maximum_volume = config[CONF_MAX_VOLUME]
    volume_step = config[CONF_VOLUME_STEP]
    inverse_speaker_mode = config[CONF_INVERSE_SPEAKER_MODE]
    supports_on = config[CONF_SUPPORTS_ON]
    standby_time = config.get(CONF_STANDBY_TIME)

    sources = SOURCES[speaker_type]

    _LOGGER.debug(
        "Setting up %s with host: %s, port: %s, name: %s, sources: %s",
        DOMAIN,
        host,
        port,
        name,
        sources,
    )

    try:
        if ipaddress.ip_address(host).version == 6:
            mode = "ip6"
        else:
            mode = "ip"
    except ValueError:
        mode = "hostname"
    mac = await hass.async_add_executor_job(partial(get_mac_address, **{mode: host}))
    unique_id = f"kef-{mac}" if mac is not None else None

    media_player = KefMediaPlayer(
        name,
        host,
        port,
        maximum_volume,
        volume_step,
        standby_time,
        inverse_speaker_mode,
        supports_on,
        sources,
        ioloop=hass.loop,
        unique_id=unique_id,
    )

    if host in hass.data[DOMAIN]:
        _LOGGER.debug("%s is already configured", host)
    else:
        hass.data[DOMAIN][host] = media_player
        async_add_entities([media_player], update_before_add=True)


class KefMediaPlayer(MediaPlayerDevice):
    """Kef Player Object."""

    def __init__(
        self,
        name,
        host,
        port,
        maximum_volume,
        volume_step,
        standby_time,
        inverse_speaker_mode,
        supports_on,
        sources,
        ioloop,
        unique_id,
    ):
        """Initialize the media player."""
        self._name = name
        self._sources = sources
        self._speaker = AsyncKefSpeaker(
            host,
            port,
            volume_step,
            maximum_volume,
            standby_time,
            inverse_speaker_mode,
            ioloop=ioloop,
        )
        self._unique_id = unique_id
        self._supports_on = supports_on

        self._state = None
        self._muted = None
        self._source = None
        self._volume = None
        self._is_online = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    async def async_update(self):
        """Update latest state."""
        _LOGGER.debug("Running async_update")
        try:
            self._is_online = await self._speaker.is_online()
            if self._is_online:
                (
                    self._volume,
                    self._muted,
                ) = await self._speaker.get_volume_and_is_muted()
                state = await self._speaker.get_state()
                self._source = state.source
                self._state = STATE_ON if state.is_on else STATE_OFF
            else:
                self._muted = None
                self._source = None
                self._volume = None
                self._state = STATE_OFF
        except (ConnectionRefusedError, ConnectionError, TimeoutError) as err:
            _LOGGER.debug("Error in `update`: %s", err)
            self._state = None

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        support_kef = (
            SUPPORT_VOLUME_SET
            | SUPPORT_VOLUME_STEP
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_SELECT_SOURCE
            | SUPPORT_TURN_OFF
            | SUPPORT_NEXT_TRACK  # only in Bluetooth and Wifi
            | SUPPORT_PAUSE  # only in Bluetooth and Wifi
            | SUPPORT_PLAY  # only in Bluetooth and Wifi
            | SUPPORT_PREVIOUS_TRACK  # only in Bluetooth and Wifi
        )
        if self._supports_on:
            support_kef |= SUPPORT_TURN_ON

        return support_kef

    @property
    def source(self):
        """Name of the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._sources

    @property
    def available(self):
        """Return if the speaker is reachable online."""
        return self._is_online

    @property
    def unique_id(self):
        """Return the device unique id."""
        return self._unique_id

    @property
    def icon(self):
        """Return the device's icon."""
        return "mdi:speaker-wireless"

    async def async_turn_off(self):
        """Turn the media player off."""
        await self._speaker.turn_off()

    async def async_turn_on(self):
        """Turn the media player on."""
        if not self._supports_on:
            raise NotImplementedError()
        await self._speaker.turn_on()

    async def async_volume_up(self):
        """Volume up the media player."""
        await self._speaker.increase_volume()

    async def async_volume_down(self):
        """Volume down the media player."""
        await self._speaker.decrease_volume()

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self._speaker.set_volume(volume)

    async def async_mute_volume(self, mute):
        """Mute (True) or unmute (False) media player."""
        if mute:
            await self._speaker.mute()
        else:
            await self._speaker.unmute()

    async def async_select_source(self, source: str):
        """Select input source."""
        if source in self.source_list:
            await self._speaker.set_source(source)
        else:
            raise ValueError(f"Unknown input source: {source}.")

    async def async_media_play(self):
        """Send play command."""
        await self._speaker.play_pause()

    async def async_media_pause(self):
        """Send pause command."""
        await self._speaker.play_pause()

    async def async_media_previous_track(self):
        """Send previous track command."""
        await self._speaker.prev_track()

    async def async_media_next_track(self):
        """Send next track command."""
        await self._speaker.next_track()
