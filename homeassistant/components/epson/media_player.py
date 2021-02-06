"""Support for Epson projector."""
from datetime import timedelta
import logging
from typing import Any, Dict, Optional

from epson_projector import Projector
from epson_projector.const import (
    BACK,
    BUSY,
    CMODE,
    CMODE_LIST,
    CMODE_LIST_SET,
    DEFAULT_SOURCES,
    EPSON_CODES,
    FAST,
    INV_SOURCES,
    MUTE,
    PAUSE,
    PLAY,
    POWER,
    SOURCE,
    SOURCE_LIST,
    STATE_UNAVAILABLE as EPSON_STATE_UNAVAILABLE,
    TURN_OFF,
    TURN_ON,
    VOL_DOWN,
    VOL_UP,
    VOLUME,
)

from homeassistant.components.media_player import DEVICE_CLASS_TV, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)

from .const import ATTR_COLOR_MODE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Epson projector from a config entry."""
    projector = EpsonProjector(
        config_entry.title,
        config_entry.data,
        unique_id=config_entry.entry_id,
        websession=async_get_clientsession(hass, verify_ssl=False),
    )
    async_add_entities([projector], True)


async def async_setup_platform(
    hass: HomeAssistantType,
    _: ConfigType,
    async_add_entities,
    discovery_info: Optional[DiscoveryInfoType] = None,
):
    """Read configuration and set up the Epson projector."""
    if discovery_info is None:
        return

    projectors = []
    for projector in discovery_info:
        # noinspection PyTypeChecker
        projectors.append(
            EpsonProjector(
                projector[CONF_NAME],
                projector,
                websession=async_get_clientsession(hass, verify_ssl=False),
            )
        )

    async_add_entities(projectors)


class EpsonProjector(MediaPlayerEntity):
    """Representation of Epson Projector Device."""

    def __init__(self, name, config: Dict[str, Any], unique_id=None, websession=None):
        """Initialize entity to control Epson projector."""
        self._name = name
        self._available = False
        self._color_mode = None
        self._source_list = list(DEFAULT_SOURCES.values())
        self._source = None
        self._volume = None
        self._state = None
        self._unique_id = unique_id
        self._scan_interval = timedelta(seconds=config[CONF_SCAN_INTERVAL])

        self._projector = Projector(
            host=config[CONF_HOST],
            websession=websession,
            port=config[CONF_PORT],
            type=config[CONF_PROTOCOL],
        )

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        async_track_time_interval(self.hass, self._async_update, self._scan_interval)

    async def _async_update(self, _):
        """Update state of device."""
        power_state = await self._projector.get_property(POWER)
        _LOGGER.debug("Projector status: %s", power_state)
        if not power_state or power_state == EPSON_STATE_UNAVAILABLE:
            self._available = False
            return
        self._available = True
        if power_state == EPSON_CODES[POWER]:
            self._state = STATE_ON
            self._source_list = list(DEFAULT_SOURCES.values())
            color_mode = await self._projector.get_property(CMODE)
            self._color_mode = CMODE_LIST.get(color_mode, self._color_mode)
            source = await self._projector.get_property(SOURCE)
            self._source = SOURCE_LIST.get(source, self._source)
            volume = await self._projector.get_property(VOLUME)
            if volume:
                self._volume = volume
        elif power_state == BUSY:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def available(self):
        """Return if projector is available."""
        return self._available

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return (
            SUPPORT_TURN_ON
            | SUPPORT_TURN_OFF
            | SUPPORT_SELECT_SOURCE
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_VOLUME_STEP
            | SUPPORT_NEXT_TRACK
            | SUPPORT_PREVIOUS_TRACK
        )

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the projector."""
        return DEVICE_CLASS_TV

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """

        # Handle polling directly in this entity
        return False

    async def async_turn_on(self):
        """Turn on epson."""
        if self._state == STATE_OFF:
            await self._projector.send_command(TURN_ON)

    async def async_turn_off(self):
        """Turn off epson."""
        if self._state == STATE_ON:
            await self._projector.send_command(TURN_OFF)

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def source(self):
        """Get current input sources."""
        return self._source

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return self._volume

    async def select_color_mode(self, color_mode):
        """Set color mode in Epson."""
        await self._projector.send_command(CMODE_LIST_SET[color_mode])

    async def async_select_source(self, source):
        """Select input source."""
        selected_source = INV_SOURCES[source]
        await self._projector.send_command(selected_source)

    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) sound."""
        await self._projector.send_command(MUTE)

    async def async_volume_up(self):
        """Increase volume."""
        await self._projector.send_command(VOL_UP)

    async def async_volume_down(self):
        """Decrease volume."""
        await self._projector.send_command(VOL_DOWN)

    async def async_media_play(self):
        """Play media via Epson."""
        await self._projector.send_command(PLAY)

    async def async_media_pause(self):
        """Pause media via Epson."""
        await self._projector.send_command(PAUSE)

    async def async_media_next_track(self):
        """Skip to next."""
        await self._projector.send_command(FAST)

    async def async_media_previous_track(self):
        """Skip to previous."""
        await self._projector.send_command(BACK)

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        if self._color_mode is None:
            return {}
        return {ATTR_COLOR_MODE: self._color_mode}
