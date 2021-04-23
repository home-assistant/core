"""Support for Epson projector."""
import logging

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
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import ATTR_CMODE, DEFAULT_NAME, DOMAIN, SERVICE_SELECT_CMODE

_LOGGER = logging.getLogger(__name__)

SUPPORT_EPSON = (
    SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PREVIOUS_TRACK
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Epson projector from a config entry."""
    entry_id = config_entry.entry_id
    unique_id = config_entry.unique_id
    projector = hass.data[DOMAIN][entry_id]
    projector_entity = EpsonProjectorMediaPlayer(
        projector=projector,
        name=config_entry.title,
        unique_id=unique_id,
        entry=config_entry,
    )
    async_add_entities([projector_entity], True)
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_SELECT_CMODE,
        {vol.Required(ATTR_CMODE): vol.All(cv.string, vol.Any(*CMODE_LIST_SET))},
        SERVICE_SELECT_CMODE,
    )


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Epson projector."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def set_new_unique_id(hass, uid, entry):
    """Set new unique id."""
    hass.config_entries.async_update_entry(entry, unique_id=uid)
    registry = async_get_entity_registry(hass)
    old_entity_id = registry.async_get_entity_id("media_player", DOMAIN, entry.entry_id)
    registry.async_update_entity(old_entity_id, new_unique_id=uid)
    hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


class EpsonProjectorMediaPlayer(MediaPlayerEntity):
    """Representation of Epson Projector Device."""

    def __init__(self, projector, name, unique_id, entry):
        """Initialize entity to control Epson projector."""
        self._projector = projector
        self._entry = entry
        self._name = name
        self._available = False
        self._cmode = None
        self._source_list = list(DEFAULT_SOURCES.values())
        self._source = None
        self._volume = None
        self._state = None
        self._unique_id = unique_id

    async def set_unique_id(self):
        """Set unique id for projector config entry."""
        _LOGGER.debug("Setting unique_id for projector")
        if self._unique_id:
            return False
        uid = await self._projector.get_serial_number()
        if uid:
            async_set_new_unique_id((self.hass, uid, self._entry)
            return True

    async def async_update(self):
        """Update state of device."""
        power_state = await self._projector.get_power()
        _LOGGER.debug("Projector status: %s", power_state)
        if not power_state or power_state == EPSON_STATE_UNAVAILABLE:
            self._available = False
            return
        self._available = True
        if power_state == EPSON_CODES[POWER]:
            self._state = STATE_ON
            if await self.set_unique_id():
                return
            self._source_list = list(DEFAULT_SOURCES.values())
            cmode = await self._projector.get_property(CMODE)
            self._cmode = CMODE_LIST.get(cmode, self._cmode)
            source = await self._projector.get_property(SOURCE)
            self._source = SOURCE_LIST.get(source, self._source)
            volume = await self._projector.get_property(VOLUME)
            if volume:
                self._volume = volume
        elif power_state == BUSY:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

    @property
    def device_info(self):
        """Get attributes about the device."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "manufacturer": "Epson",
            "name": "Epson projector",
            "model": "Epson",
            "via_hub": (DOMAIN, self._unique_id),
        }

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
        return SUPPORT_EPSON

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

    async def select_cmode(self, cmode):
        """Set color mode in Epson."""
        await self._projector.send_command(CMODE_LIST_SET[cmode])

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
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        if self._cmode is None:
            return {}
        return {ATTR_CMODE: self._cmode}
