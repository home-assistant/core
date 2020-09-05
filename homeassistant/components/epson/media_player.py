"""Support for Epson projector."""
import logging

import epson_projector as epson
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
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import (
    ATTR_CMODE,
    DATA_EPSON,
    DEFAULT_NAME,
    DOMAIN,
    SERVICE_SELECT_CMODE,
    SUPPORT_CMODE,
    TIMEOUT_SCALE,
)

SIGNAL_CONFIG_OPTIONS_UPDATE = "epson_config_options_update {}"

_LOGGER = logging.getLogger(__name__)


SUPPORT_ONKYO = (
    SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
)

SUPPORT_EPSON = (
    SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_CMODE
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PREVIOUS_TRACK
)

MEDIA_PLAYER_SCHEMA = vol.Schema({ATTR_ENTITY_ID: cv.comp_entity_ids})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
    }
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Epson from a config entry."""

    timeout_scale = config_entry.options.get(TIMEOUT_SCALE, 1.0)
    epson_proj = EpsonProjector(
        async_get_clientsession(
            hass, verify_ssl=config_entry.data.get(CONF_SSL, False)
        ),
        config_entry.title,
        config_entry.data[CONF_HOST],
        config_entry.data[CONF_PORT],
        timeout_scale,
        config_entry.entry_id,
    )
    if not hass.data.get(DOMAIN):
        hass.data[DOMAIN] = {config_entry.entry_id: {}}
    if DATA_EPSON not in hass.data:
        hass.data[DATA_EPSON] = []

    hass.data[DOMAIN][config_entry.entry_id] = config_entry.add_update_listener(
        update_listener
    )
    hass.data[DATA_EPSON].append(epson_proj)
    async_add_entities([epson_proj])

    async def async_service_handler(service):
        """Handle for services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            devices = [
                device
                for device in hass.data[DATA_EPSON]
                if device.entity_id in entity_ids
            ]
        else:
            devices = hass.data[DATA_EPSON]
        for device in devices:
            if service.service == SERVICE_SELECT_CMODE:
                cmode = service.data.get(ATTR_CMODE)
                await device.select_cmode(cmode)
            device.async_schedule_update_ha_state(True)

    epson_schema = MEDIA_PLAYER_SCHEMA.extend(
        {vol.Required(ATTR_CMODE): vol.All(cv.string, vol.Any(*CMODE_LIST_SET))}
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SELECT_CMODE, async_service_handler, schema=epson_schema
    )
    return True


async def update_listener(hass, entry):
    """Handle options update."""
    async_dispatcher_send(
        hass, SIGNAL_CONFIG_OPTIONS_UPDATE.format(entry.entry_id), entry.options
    )


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Epson Platform."""
    pass


class EpsonProjector(MediaPlayerEntity):
    """Representation of Epson Projector Device."""

    def __init__(self, websession, name, host, port, timeout_scale, entry_id):
        """Initialize entity to control Epson projector."""
        self._name = name
        self._projector = epson.Projector(
            host, websession=websession, port=port, timeout_scale=timeout_scale
        )
        self._cmode = None
        self._source_list = list(DEFAULT_SOURCES.values())
        self._source = None
        self._volume = None
        self._state = None
        self._entry_id = entry_id

    async def async_update(self):
        """Update state of device."""
        is_turned_on = await self._projector.get_property(POWER)
        _LOGGER.debug("Projector status: %s", is_turned_on)
        if is_turned_on and is_turned_on == EPSON_CODES[POWER]:
            self._state = STATE_ON
            cmode = await self._projector.get_property(CMODE)
            self._cmode = CMODE_LIST.get(cmode, self._cmode)
            source = await self._projector.get_property(SOURCE)
            self._source = SOURCE_LIST.get(source, self._source)
            volume = await self._projector.get_property(VOLUME)
            if volume:
                self._volume = volume
        elif is_turned_on == BUSY:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

    async def async_added_to_hass(self):
        """Use lifecycle hooks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_CONFIG_OPTIONS_UPDATE.format(self._entry_id),
                self.update_options,
            )
        )

    @callback
    def update_options(self, options):
        """Update timeout scale option."""
        self._projector.set_timeout_scale(options.get(TIMEOUT_SCALE, 1.0))

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ONKYO

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
    def device_state_attributes(self):
        """Return device specific state attributes."""
        if self._cmode is None:
            return {}
        return {ATTR_CMODE: self._cmode}
