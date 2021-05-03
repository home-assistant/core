"""Platform for the KEF Wireless Speakers."""

from datetime import timedelta
from functools import partial
import ipaddress
import logging

from aiokef import AsyncKefSpeaker
from aiokef.aiokef import DSP_OPTION_MAPPING
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
    MediaPlayerEntity,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.event import async_track_time_interval

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

SERVICE_MODE = "set_mode"
SERVICE_DESK_DB = "set_desk_db"
SERVICE_WALL_DB = "set_wall_db"
SERVICE_TREBLE_DB = "set_treble_db"
SERVICE_HIGH_HZ = "set_high_hz"
SERVICE_LOW_HZ = "set_low_hz"
SERVICE_SUB_DB = "set_sub_db"
SERVICE_UPDATE_DSP = "update_dsp"

DSP_SCAN_INTERVAL = timedelta(seconds=3600)

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


def get_ip_mode(host):
    """Get the 'mode' used to retrieve the MAC address."""
    try:
        if ipaddress.ip_address(host).version == 6:
            return "ip6"
        return "ip"
    except ValueError:
        return "hostname"


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

    mode = get_ip_mode(host)
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
        speaker_type,
        loop=hass.loop,
        unique_id=unique_id,
    )

    if host in hass.data[DOMAIN]:
        _LOGGER.debug("%s is already configured", host)
    else:
        hass.data[DOMAIN][host] = media_player
        async_add_entities([media_player], update_before_add=True)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_MODE,
        {
            vol.Optional("desk_mode"): cv.boolean,
            vol.Optional("wall_mode"): cv.boolean,
            vol.Optional("phase_correction"): cv.boolean,
            vol.Optional("high_pass"): cv.boolean,
            vol.Optional("sub_polarity"): vol.In(["-", "+"]),
            vol.Optional("bass_extension"): vol.In(["Less", "Standard", "Extra"]),
        },
        "set_mode",
    )
    platform.async_register_entity_service(SERVICE_UPDATE_DSP, {}, "update_dsp")

    def add_service(name, which, option):
        options = DSP_OPTION_MAPPING[which]
        dtype = type(options[0])  # int or float
        platform.async_register_entity_service(
            name,
            {
                vol.Required(option): vol.All(
                    vol.Coerce(float), vol.Coerce(dtype), vol.In(options)
                )
            },
            f"set_{which}",
        )

    add_service(SERVICE_DESK_DB, "desk_db", "db_value")
    add_service(SERVICE_WALL_DB, "wall_db", "db_value")
    add_service(SERVICE_TREBLE_DB, "treble_db", "db_value")
    add_service(SERVICE_HIGH_HZ, "high_hz", "hz_value")
    add_service(SERVICE_LOW_HZ, "low_hz", "hz_value")
    add_service(SERVICE_SUB_DB, "sub_db", "db_value")


class KefMediaPlayer(MediaPlayerEntity):
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
        speaker_type,
        loop,
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
            loop=loop,
        )
        self._unique_id = unique_id
        self._supports_on = supports_on
        self._speaker_type = speaker_type

        self._state = None
        self._muted = None
        self._source = None
        self._volume = None
        self._is_online = None
        self._dsp = None
        self._update_dsp_task_remover = None

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
                if self._dsp is None:
                    # Only do this when necessary because it is a slow operation
                    await self.update_dsp()
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
        await self._speaker.set_play_pause()

    async def async_media_pause(self):
        """Send pause command."""
        await self._speaker.set_play_pause()

    async def async_media_previous_track(self):
        """Send previous track command."""
        await self._speaker.prev_track()

    async def async_media_next_track(self):
        """Send next track command."""
        await self._speaker.next_track()

    async def update_dsp(self, _=None) -> None:
        """Update the DSP settings."""
        if self._speaker_type == "LS50" and self._state == STATE_OFF:
            # The LSX is able to respond when off the LS50 has to be on.
            return

        mode = await self._speaker.get_mode()
        self._dsp = dict(
            desk_db=await self._speaker.get_desk_db(),
            wall_db=await self._speaker.get_wall_db(),
            treble_db=await self._speaker.get_treble_db(),
            high_hz=await self._speaker.get_high_hz(),
            low_hz=await self._speaker.get_low_hz(),
            sub_db=await self._speaker.get_sub_db(),
            **mode._asdict(),
        )

    async def async_added_to_hass(self):
        """Subscribe to DSP updates."""
        self._update_dsp_task_remover = async_track_time_interval(
            self.hass, self.update_dsp, DSP_SCAN_INTERVAL
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe to DSP updates."""
        self._update_dsp_task_remover()
        self._update_dsp_task_remover = None

    @property
    def extra_state_attributes(self):
        """Return the DSP settings of the KEF device."""
        return self._dsp or {}

    async def set_mode(
        self,
        desk_mode=None,
        wall_mode=None,
        phase_correction=None,
        high_pass=None,
        sub_polarity=None,
        bass_extension=None,
    ):
        """Set the speaker mode."""
        await self._speaker.set_mode(
            desk_mode=desk_mode,
            wall_mode=wall_mode,
            phase_correction=phase_correction,
            high_pass=high_pass,
            sub_polarity=sub_polarity,
            bass_extension=bass_extension,
        )
        self._dsp = None

    async def set_desk_db(self, db_value):
        """Set desk_db of the KEF speakers."""
        await self._speaker.set_desk_db(db_value)
        self._dsp = None

    async def set_wall_db(self, db_value):
        """Set wall_db of the KEF speakers."""
        await self._speaker.set_wall_db(db_value)
        self._dsp = None

    async def set_treble_db(self, db_value):
        """Set treble_db of the KEF speakers."""
        await self._speaker.set_treble_db(db_value)
        self._dsp = None

    async def set_high_hz(self, hz_value):
        """Set high_hz of the KEF speakers."""
        await self._speaker.set_high_hz(hz_value)
        self._dsp = None

    async def set_low_hz(self, hz_value):
        """Set low_hz of the KEF speakers."""
        await self._speaker.set_low_hz(hz_value)
        self._dsp = None

    async def set_sub_db(self, db_value):
        """Set sub_db of the KEF speakers."""
        await self._speaker.set_sub_db(db_value)
        self._dsp = None
