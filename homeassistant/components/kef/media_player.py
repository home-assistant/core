"""Platform for the KEF Wireless Speakers."""

import datetime
import logging

from aiokef.aiokef import INPUT_SOURCES, AsyncKefSpeaker
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
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
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.helpers import config_validation as cv

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)


DEFAULT_NAME = "KEF"
DEFAULT_PORT = 50001
DEFAULT_MAX_VOLUME = 0.5
DEFAULT_VOLUME_STEP = 0.05
DATA_KEF = "kef"

SCAN_INTERVAL = datetime.timedelta(seconds=30)
PARALLEL_UPDATES = 0

KEF_LS50_SOURCES = sorted(INPUT_SOURCES.keys())

SUPPORT_KEF = (
    SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
)

CONF_MAX_VOLUME = "maximum_volume"
CONF_VOLUME_STEP = "volume_step"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MAX_VOLUME, default=DEFAULT_MAX_VOLUME): cv.small_float,
        vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP): cv.small_float,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the KEF platform."""
    if DATA_KEF not in hass.data:
        hass.data[DATA_KEF] = {}

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    maximum_volume = config.get(CONF_MAX_VOLUME)
    volume_step = config.get(CONF_VOLUME_STEP)

    _LOGGER.debug(
        "Setting up %s with host: %s, port: %s, name: %s, sources: %s",
        DATA_KEF,
        host,
        port,
        name,
        KEF_LS50_SOURCES,
    )

    media_player = KefMediaPlayer(
        name,
        host,
        port,
        maximum_volume=maximum_volume,
        volume_step=volume_step,
        sources=KEF_LS50_SOURCES,
        ioloop=hass.loop,
    )
    unique_id = media_player.unique_id
    if unique_id in hass.data[DATA_KEF]:
        _LOGGER.debug("%s is already configured.", unique_id)
    else:
        hass.data[DATA_KEF][unique_id] = media_player
        async_add_entities([media_player], update_before_add=True)


class KefMediaPlayer(MediaPlayerDevice):
    """Kef Player Object."""

    def __init__(self, name, host, port, maximum_volume, volume_step, sources, ioloop):
        """Initialize the media player."""
        self._name = name
        self._sources = sources
        self._speaker = AsyncKefSpeaker(
            host, port, volume_step, maximum_volume, ioloop=ioloop
        )

        self._state = STATE_UNKNOWN
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
                self._source, is_on = await self._speaker.get_source_and_state()
                self._state = STATE_ON if is_on else STATE_OFF
            else:
                self._muted = None
                self._source = None
                self._volume = None
                self._state = STATE_OFF
        except (ConnectionRefusedError, ConnectionError, TimeoutError) as err:
            _LOGGER.debug("Error in `update`: %s", err)
            self._state = STATE_UNKNOWN

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
        return SUPPORT_KEF

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
        return f"{self._speaker.host}:{self._speaker.port}"

    @property
    def icon(self):
        """Return the device's icon."""
        return "mdi:speaker-wireless"

    @property
    def should_poll(self):
        """It's possible that the speaker is controlled manually."""
        return True

    @property
    def force_update(self):
        """Force update."""
        return False

    async def async_turn_off(self):
        """Turn the media player off."""
        await self._speaker.turn_off()

    async def async_turn_on(self):
        """Turn the media player on."""
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
