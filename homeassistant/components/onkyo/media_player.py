"""Support for Onkyo Network Receivers and Processors."""
from __future__ import annotations

import logging

import pyeiscp
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_PLAY_MEDIA,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, entity_platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = "onkyo"

DEFAULT_PORT = 60128

CONF_SOURCES = "sources"
CONF_MAX_VOLUME = "max_volume"

DEFAULT_NAME = "Onkyo Receiver"
SUPPORTED_MAX_VOLUME = 90
ZONES = {"zone2": "Zone 2", "zone3": "Zone 3", "zone4": "Zone 4"}

KNOWN_HOSTS: list[str] = []
DEFAULT_SOURCES = {
    "tv": "TV",
    "bd": "Bluray",
    "game": "Game",
    "aux1": "Aux1",
    "video1": "Video 1",
    "video2": "Video 2",
    "video3": "Video 3",
    "video4": "Video 4",
    "video5": "Video 5",
    "video6": "Video 6",
    "video7": "Video 7",
    "fm": "Radio",
}

SOUND_MODE_MAPPING = {
    "Auto": ["auto"],
    "Direct": ["direct"],
    "Pure Direct": ["pure-audio"],
    "Stereo": ["stereo"],
    "Extended Stereo": ["all-ch-stereo"],
    "Surround": ["surr"],
    "Auto Surround": ["auto-surround"],
    "Multichannel PCM": ["straight-decode"],
    "Dolby Digital": [
        "dolby-atmos",
        "dolby-surround",
        "dolby-virtual",
        "dolby-ex",
        "dolby-surround-thx-cinema",
        "pliix-thx-cinema",
        "pliix-movie",
        "dolby-surround-thx-music",
        "pliix-thx-music",
        "pliix-music",
        "dolby-surround-thx-games",
        "pliix-thx-games",
        "pliix-game",
        "pliiz-height-thx-cinema",
        "pliiz-height-thx-games",
        "plii",
        "pliiz-height-thx-music",
        "pliiz-height-thx-u2",
        "pliiz-height",
    ],
    "DTS Surround": [
        "dts-x",
        "neural-x",
        "dts-surround-sensation",
        "neo-6-cinema-dts-surround-sensation",
        "dts-neural-x-thx-cinema",
        "neo-6-music-dts-surround-sensation",
        "dts-neural-x-thx-music",
        "dts-neural-x-thx-games",
    ],
    "THX": [
        "thx",
        "thx-surround-ex",
        "thx-cinema",
        "thx-music",
        "thx-musicmode",
        "thx-games",
        "thx-u2",
        "neural-thx",
        "neural-thx-cinema",
        "neural-thx-music",
        "neural-thx-games",
    ],
    "Mono": ["mono"],
    "Extended Mono": ["full-mono"],
    "Action": ["action", "game-action"],
    "Drama": ["tv-logic"],
    "Entertainment Show": ["studio-mix"],
    "Advanced Game": ["film", "game-rpg"],
    "Sports": ["enhanced-7", "enhance", "game-sports"],
    "Classical": ["orchestra"],
    "Rock/Pop": ["musical", "game-rock"],
    "Unplugged": ["unplugged"],
    "Front Stage Surround": ["theater-dimensional"],
}

SOUND_MODE_REVERSE_MAPPING = {
    subval: key for key, values in SOUND_MODE_MAPPING.items() for subval in values
}

DEFAULT_PLAYABLE_SOURCES = ("fm", "am", "tuner")

SUPPORT_ONKYO = (
    SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_SELECT_SOUND_MODE
)

SUPPORT_ONKYO_WO_VOLUME = (
    SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_VOLUME_MUTE
)

SUPPORT_ONKYO_WO_SOUND_MODE = (
    SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY_MEDIA
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_MAX_VOLUME, default=SUPPORTED_MAX_VOLUME): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(CONF_SOURCES, default=DEFAULT_SOURCES): {cv.string: cv.string},
    }
)

ATTR_HDMI_OUTPUT = "hdmi_output"
ATTR_PRESET = "preset"
ATTR_AUDIO_INFORMATION = "audio_information"
ATTR_VIDEO_INFORMATION = "video_information"
ATTR_VIDEO_OUT = "video_out"

ACCEPTED_VALUES = [
    "no",
    "analog",
    "yes",
    "out",
    "out-sub",
    "sub",
    "hdbaset",
    "both",
    "up",
]

SERVICE_SELECT_HDMI_OUTPUT = "onkyo_select_hdmi_output"
AUDIO_VIDEO_INFORMATION_UPDATE_INTERVAL = 10

AUDIO_INFORMATION_MAPPING = [
    "audio_input_port",
    "input_signal_format",
    "input_frequency",
    "input_channels",
    "listening_mode",
    "output_channels",
    "output_frequency",
    "precision_quartz_lock_system",
    "auto_phase_control_delay",
    "auto_phase_control_phase",
]

VIDEO_INFORMATION_MAPPING = [
    "video_input_port",
    "input_resolution",
    "input_color_schema",
    "input_color_depth",
    "video_output_port",
    "output_resolution",
    "output_color_schema",
    "output_color_depth",
    "picture_mode",
]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up our socket to the AVR."""

    host = config.get(CONF_HOST)
    port = config[CONF_PORT]
    name = config[CONF_NAME]
    max_volume = config[CONF_MAX_VOLUME]
    sources = config[CONF_SOURCES]

    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_SELECT_HDMI_OUTPUT,
        {vol.Required(ATTR_HDMI_OUTPUT): vol.In(ACCEPTED_VALUES)},
        "async_select_output",
    )

    avrs = {}
    active_zones = {}

    def setup_avr(avr):
        KNOWN_HOSTS.append(avr.host)

        # Store the avr object and create a dictionary to store its active zones.
        avrs[avr.host] = avr
        active_zones[avr.host] = {}

        # Discover what zones are available for the avr by querying the power.
        # If we get a response for the specific zone, it means it is available.
        for zone in ZONES:
            avr.query_property(zone, "power")

        # Add the main zone to active_zones, since it is always active
        main_entity = OnkyoAVR(
            avr, avr.name, avr.identifier, sources, "main", max_volume
        )
        active_zones[avr.host]["main"] = main_entity
        async_add_entities([main_entity])

    def async_onkyo_discover_zones_callback(avr, zone):
        """Receive the power status of the available zones on the AVR."""
        # When we receive the status for a zone, it is available on the AVR
        # So we create an entity for the zone and add it to active_zones
        if zone in ZONES:
            _LOGGER.debug("Discovered %s on %s,", ZONES[zone], avr.name)
            zone_entity = OnkyoAVR(
                avr, avr.name, avr.identifier, sources, zone, max_volume
            )
            active_zones[avr.host][zone] = zone_entity
            async_add_entities([zone_entity])

    @callback
    def async_onkyo_update_callback(message, origin=None):
        """Receive notification from transport that new data exists."""
        _host = origin or host
        _LOGGER.debug("Received update callback from %s: %s", avrs[_host].name, message)

        zone, _, _ = message
        if zone in active_zones[_host]:
            active_zones[_host][zone].process_update(message)
        else:
            async_onkyo_discover_zones_callback(avrs[_host], zone)

    @callback
    def async_onkyo_connect_callback():
        """Receiver (re)connected."""
        _LOGGER.debug("AVR (re)connected:")
        for avr in active_zones.values():
            for zone in avr.values():
                zone.backfill_state()

    @callback
    async def async_onkyo_discovery_callback(avr):
        """Receiver discovered, connection not yet active."""
        if avr.host not in KNOWN_HOSTS:
            try:
                await avr.connect()
            except Exception:
                raise PlatformNotReady from Exception

            setup_avr(avr)

    if CONF_HOST in config and host not in KNOWN_HOSTS:
        # If a host is specified, try to create a single connection to that host
        try:
            avr = await pyeiscp.Connection.create(
                host=host,
                port=port,
                update_callback=async_onkyo_update_callback,
                connect_callback=async_onkyo_connect_callback,
            )
        except Exception:
            raise PlatformNotReady from Exception

        # The library only automatically adds a name and identifier on discovered avrs.
        # So manually add them here to be use for zone discovery later.
        avr.name = name
        avr.identifier = None

        setup_avr(avr)

    else:
        # If no host is specified, create connections for all discovered receivers
        await pyeiscp.Connection.discover(
            port=port,
            update_callback=async_onkyo_update_callback,
            connect_callback=async_onkyo_connect_callback,
            discovery_callback=async_onkyo_discovery_callback,
        )

    @callback
    def close_avr(_event):
        for avr in avrs.values():
            avr.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_avr)


class OnkyoAVR(MediaPlayerEntity):
    """Entity reading values from Onkyo AVR protocol."""

    def __init__(self, avr, name, identifier, sources, zone, max_volume):
        """Initialize entity with transport."""
        super().__init__()
        self._avr = avr
        self._name = f"{name} {ZONES[zone] if zone != 'main' else ''}"
        if identifier is not None:
            self._unique_id = f"{identifier}_{zone}"
        else:
            self._unique_id = None

        self._zone = zone
        self._volume = 0
        self._supports_volume = False
        self._muted = False
        self._max_volume = max_volume
        self._powerstate = STATE_UNKNOWN
        self._source = None
        self._source_list = list(sources.values())
        self._source_mapping = sources
        self._reverse_mapping = {value: key for key, value in sources.items()}
        self._sound_mode = None
        self._attributes = {}
        self._supports_sound_mode = False
        self._supports_audio_info = False
        self._supports_video_info = False
        self._query_timer = None

    async def async_added_to_hass(self):
        """Entity has been added to hass."""
        self.backfill_state()

    async def async_will_remove_from_hass(self):
        """Cancel the query timer when the entity is removed."""
        if self._query_timer:
            self._query_timer()
            self._query_timer = None

    @callback
    def process_update(self, update):
        """Store relevant updates so they can be queried later."""
        zone, command, value = update
        if zone != self._zone:
            return

        if command in ["system-power", "power"]:
            if value == "on":
                self._powerstate = STATE_ON
            else:
                self._powerstate = STATE_OFF
                self._attributes.pop(ATTR_AUDIO_INFORMATION, None)
                self._attributes.pop(ATTR_VIDEO_INFORMATION, None)
                self._attributes.pop(ATTR_PRESET, None)
                self._attributes.pop(ATTR_VIDEO_OUT, None)

        elif command in ["volume", "master-volume"] and value != "N/A":
            self._supports_volume = True
            self._volume = min(value / self._max_volume, 1)
        elif command in ["muting", "audio-muting"]:
            self._muted = bool(value == "on")
        elif command in ["selector", "input-selector"]:
            self._parse_source(value)
            self._query_delayed_av_info()
        elif command == "hdmi-output-selector":
            self._attributes[ATTR_VIDEO_OUT] = ",".join(value)
        elif command == "preset":
            if not (self._source is None) and self._source.lower() == "radio":
                self._attributes[ATTR_PRESET] = value
            elif ATTR_PRESET in self._attributes:
                del self._attributes[ATTR_PRESET]
        elif command == "listening-mode":
            self._supports_sound_mode = True
            self._parse_sound_mode(value)
        elif command == "audio-information":
            self._supports_audio_info = True
            self._parse_audio_inforamtion(value)
        elif command == "video-information":
            self._supports_video_info = True
            self._parse_video_inforamtion(value)
        elif command == "fl-display-information":
            self._query_delayed_av_info()

        self.async_write_ha_state()

    @callback
    def backfill_state(self):
        """Get the receiver to send all the info we care about.

        Usually run only on connect, as we can otherwise rely on the
        receiver to keep us informed of changes.
        """
        self._query_avr("power")
        self._query_avr("volume")
        self._query_avr("preset")
        if self._zone == "main":
            self._query_avr("hdmi-output-selector")
            self._query_avr("audio-muting")
            self._query_avr("input-selector")
            self._query_avr("listening-mode")
            self._query_avr("audio-information")
            self._query_avr("video-information")
        else:
            self._query_avr("muting")
            self._query_avr("selector")

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._supports_sound_mode:
            return SUPPORT_ONKYO
        if self._supports_volume:
            return SUPPORT_ONKYO_WO_SOUND_MODE
        return SUPPORT_ONKYO_WO_VOLUME

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._unique_id

    @property
    def name(self):
        """Return name of device."""
        return self._name

    @property
    def state(self):
        """Return state of power on/off."""
        return self._powerstate

    @property
    def is_volume_muted(self):
        """Return boolean reflecting mute state on device."""
        return self._muted

    @property
    def volume_level(self):
        """Return volume level from 0 to 1."""
        return self._volume

    @property
    def source(self):
        """Return currently selected input."""
        return self._source

    @property
    def source_list(self):
        """Return all active, configured inputs."""
        return self._source_list

    @property
    def sound_mode(self):
        """Return the current matched sound mode."""
        return self._sound_mode

    @property
    def sound_mode_list(self):
        """Return a list of available sound modes."""
        return list(SOUND_MODE_MAPPING)

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return self._attributes

    async def async_select_source(self, source):
        """Change AVR to the designated source (by name)."""
        if source in self._source_list:
            source = self._reverse_mapping[source]
        self._update_avr(
            "input-selector" if self._zone == "main" else "selector", source
        )

    async def async_select_sound_mode(self, sound_mode):
        """Change AVR to the designated sound_mode (by name)."""
        if sound_mode in list(SOUND_MODE_MAPPING):
            sound_mode = SOUND_MODE_MAPPING[sound_mode][0]
        self._update_avr("listening-mode", sound_mode)

    async def async_turn_off(self):
        """Turn AVR power off."""
        self._update_avr("power", "standby")

    async def async_turn_on(self):
        """Turn AVR power on."""
        self._update_avr("power", "on")

    async def async_volume_up(self):
        """Increment volume by 1."""
        if self._volume < self._max_volume:
            self._update_avr("volume", "level-up")

    async def async_volume_down(self):
        """Decrement volume by 1."""
        self._update_avr("volume", "level-down")

    async def async_set_volume_level(self, volume):
        """Set AVR volume (0 to 1)."""
        self._update_avr("volume", int(volume * self._max_volume))

    async def async_mute_volume(self, mute):
        """Engage AVR mute."""
        self._update_avr(
            "audio-muting" if self._zone == "main" else "muting",
            "on" if mute else "off",
        )

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play radio station by preset number."""
        source = self._reverse_mapping[self._source]
        if media_type.lower() == "radio" and source in DEFAULT_PLAYABLE_SOURCES:
            self._update_avr("preset", media_id)

    async def async_select_output(self, hdmi_output):
        """Set hdmi-out."""
        self._update_avr("hdmi-output-selector", hdmi_output)

    @callback
    def _parse_source(self, source):
        # source is either a tuple of values or a single value,
        # so we convert to a tuple when it is a single value
        if not isinstance(source, tuple):
            source = (source,)
        for value in source:
            if value in self._source_mapping:
                self._source = self._source_mapping[value]
                break
            self._source = "_".join(source)

    @callback
    def _parse_sound_mode(self, sound_mode):
        # If the selected sound mode is not available, N/A is returned
        # so only update the sound mode when it is not N/A
        # Also, sound_mode is either a tuple of values or a single value,
        # so we convert to a tuple when it is a single value
        if sound_mode != "N/A":
            if not isinstance(sound_mode, tuple):
                sound_mode = (sound_mode,)
            for value in sound_mode:
                if value in SOUND_MODE_REVERSE_MAPPING:
                    self._sound_mode = SOUND_MODE_REVERSE_MAPPING[value]
                    break
                self._sound_mode = "_".join(sound_mode)

    @callback
    def _parse_audio_inforamtion(self, audio_information):
        # If audio information is not available, N/A is returned
        # so only update the audio information when it is not N/A
        if audio_information == "N/A":
            self._attributes.pop(ATTR_AUDIO_INFORMATION, None)
            return

        self._attributes[ATTR_AUDIO_INFORMATION] = {
            name: value
            for name, value in zip(AUDIO_INFORMATION_MAPPING, audio_information)
            if len(value) > 0
        }

    @callback
    def _parse_video_inforamtion(self, video_information):
        # If video information is not available, N/A is returned
        # so only update the video information when it is not N/A
        if video_information == "N/A":
            self._attributes.pop(ATTR_VIDEO_INFORMATION, None)
            return

        self._attributes[ATTR_VIDEO_INFORMATION] = {
            name: value
            for name, value in zip(VIDEO_INFORMATION_MAPPING, video_information)
            if len(value) > 0
        }

    def _query_delayed_av_info(self):
        if self._zone == "main" and not self._query_timer:
            self._query_timer = self.hass.loop.call_later(
                AUDIO_VIDEO_INFORMATION_UPDATE_INTERVAL, self._query_av_info
            )

    @callback
    def _query_av_info(self):
        if self._supports_audio_info:
            self._query_avr("audio-information")
        if self._supports_video_info:
            self._query_avr("video-information")
        self._query_timer = None

    @callback
    def _update_avr(self, propname, value):
        """Update a property in the AVR."""
        self._avr.update_property(self._zone, propname, value)

    @callback
    def _query_avr(self, propname):
        """Cause the AVR to send an update about propname."""
        self._avr.query_property(self._zone, propname)
