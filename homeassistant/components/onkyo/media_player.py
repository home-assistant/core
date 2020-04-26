#!/usr/bin/python3
"""Support for Onkyo Network Receivers and Processors."""
import logging

import pyeiscp
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerDevice
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
    ATTR_ENTITY_ID,
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
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "onkyo"

DEFAULT_PORT = 60128

CONF_SOURCES = "sources"
CONF_MAX_VOLUME = "max_volume"
CONF_ZONES = "zones"

DEFAULT_NAME = "Onkyo Receiver"
SUPPORTED_MAX_VOLUME = 90
ZONES = ["zone2", "zone3", "zone4"]

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
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE | SUPPORT_PLAY_MEDIA
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
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_MAX_VOLUME, default=SUPPORTED_MAX_VOLUME): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(CONF_SOURCES, default=DEFAULT_SOURCES): {cv.string: cv.string},
        vol.Optional(CONF_ZONES, default=[]): vol.All(cv.ensure_list, [vol.In(ZONES)]),
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
ONKYO_SELECT_OUTPUT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_HDMI_OUTPUT): vol.In(ACCEPTED_VALUES),
    }
)

SERVICE_SELECT_HDMI_OUTPUT = "onkyo_select_hdmi_output"


@callback
def _parse_onkyo_tuple(value):
    """Parse a value returned from the eiscp library into a tuple."""
    if isinstance(value, str):
        return value.split(",")

    return value


@callback
def _tuple_get(tup, index, default=None):
    """Return a tuple item at index or a default value if it doesn't exist."""
    return (tup[index : index + 1] or [default])[0]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up our socket to the AVR."""

    host = config[CONF_HOST]
    port = config[CONF_PORT]
    name = config.get(CONF_NAME) or "Onkyo Receiver"
    max_volume = config[CONF_MAX_VOLUME]
    zones = config[CONF_ZONES]
    sources = config[CONF_SOURCES]

    def service_handle(service):
        """Handle for services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        devices = [d for d in active_zones.values() if d.entity_id in entity_ids]

        for device in devices:
            if service.service == SERVICE_SELECT_HDMI_OUTPUT:
                device.select_output(service.data.get(ATTR_HDMI_OUTPUT))

    hass.services.async_register(
        DOMAIN,
        SERVICE_SELECT_HDMI_OUTPUT,
        service_handle,
        schema=ONKYO_SELECT_OUTPUT_SCHEMA,
    )

    _LOGGER.debug("Provisioning Onkyo AVR device at %s:%d", host, port)

    @callback
    def async_onkyo_update_callback(message):
        """Receive notification from transport that new data exists."""
        _LOGGER.debug("Received update callback from AVR: %s", message)
        zone, _, _ = message
        if zone in active_zones.keys():
            active_zones[zone].process_update(message)
            active_zones[zone].async_write_ha_state()

    try:
        avr = await pyeiscp.Connection.create(
            host=host, port=port, update_callback=async_onkyo_update_callback
        )
    except Exception:
        raise PlatformNotReady

    active_zones = {}

    for zone in ["main"] + zones:
        active_zones[zone] = OnkyoAVR(avr, name, sources, zone, max_volume)

    @callback
    def close_avr(_event):
        for zone in active_zones.values():
            zone.avr.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_avr)

    for zone in active_zones.values():
        zone.backfill_state()

    async_add_entities(active_zones.values())


class OnkyoAVR(MediaPlayerDevice):
    """Entity reading values from Onkyo AVR protocol."""

    def __init__(self, avr, name, sources, zone, max_volume):
        """Initialize entity with transport."""
        super().__init__()
        self.avr = avr
        self._name = f"{name} {zone if zone != 'main' else ''}"
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
        self._query_timer = None

    @callback
    def process_update(self, update):
        """Store relevant updates so they can be queried later."""
        _, command, value = update
        if command in ["system-power", "power"]:
            if value == "on":
                self._powerstate = STATE_ON
            else:
                self._powerstate = STATE_OFF
                self._attributes.pop(ATTR_AUDIO_INFORMATION, None)
                self._attributes.pop(ATTR_VIDEO_INFORMATION, None)
                self._attributes.pop(ATTR_PRESET, None)
                self._attributes.pop(ATTR_VIDEO_OUT, None)

        elif command in ["volume", "master-volume"]:
            self._supports_volume = True
            self._volume = min(value / self._max_volume, 1)
        elif command == "audio-muting":
            self._muted = bool(value == "on")
        elif command == "input-selector":
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
            self._parse_audio_inforamtion(value)
        elif command == "video-information":
            self._parse_video_inforamtion(value)
        elif command == "fl-display-information":
            self._query_delayed_av_info()

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
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return self._attributes

    async def async_select_source(self, source):
        """Change AVR to the designated source (by name)."""
        if source in self._source_list:
            source = self._reverse_mapping[source]
        self._update_avr("input-selector", source)

    async def async_select_sound_mode(self, sound_mode):
        """Change AVR to the designated sound_mode (by name)."""
        if sound_mode in list(SOUND_MODE_MAPPING):
            sound_mode = SOUND_MODE_MAPPING[sound_mode][0]
        self._update_avr("listening-mode", sound_mode)

    async def async_turn_off(self):
        """Turn AVR power off."""
        self._update_avr("power", "off")

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
        self._update_avr("audio-muting", "on" if mute else "off")

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play radio station by preset number."""
        source = self._reverse_mapping[self._source]
        if media_type.lower() == "radio" and source in DEFAULT_PLAYABLE_SOURCES:
            self._update_avr("preset", media_id)

    async def async_select_output(self, output):
        """Set hdmi-out."""
        self._update_avr("hdmi-output-selector", output)

    def _update_avr(self, propname, value):
        """Update a property in the AVR."""
        self.avr.send(f"{self._zone}.{propname}={value}")

    def _query_avr(self, propname):
        """Cause the AVR to send an update about propname."""
        self.avr.send(f"{self._zone}.{propname}=query")

    @callback
    def _parse_source(self, source_raw):
        values = _parse_onkyo_tuple(source_raw)

        for source in values:
            if source in self._source_mapping:
                self._source = self._source_mapping[source]
                break
            self._source = "_".join(values)

    @callback
    def _parse_sound_mode(self, sound_mode_raw):
        values = _parse_onkyo_tuple(sound_mode_raw)

        # If the selected sound mode is not available, N/A is returned
        # so only update the sound mode when it is not N/A
        if "N/A" not in values:
            for sound_mode in values:
                if sound_mode in SOUND_MODE_REVERSE_MAPPING:
                    self._sound_mode = SOUND_MODE_REVERSE_MAPPING[sound_mode]
                    break
                self._sound_mode = "_".join(values)

    @callback
    def _parse_audio_inforamtion(self, audio_information_raw):
        values = _parse_onkyo_tuple(audio_information_raw)
        if "N/A" not in values:
            info = {
                "format": _tuple_get(values, 1),
                "input_frequency": _tuple_get(values, 2),
                "input_channels": _tuple_get(values, 3),
                "listening_mode": _tuple_get(values, 4),
                "output_channels": _tuple_get(values, 5),
                "output_frequency": _tuple_get(values, 6),
            }
            self._attributes[ATTR_AUDIO_INFORMATION] = info
        else:
            self._attributes.pop(ATTR_AUDIO_INFORMATION, None)

    @callback
    def _parse_video_inforamtion(self, video_information_raw):
        values = _parse_onkyo_tuple(video_information_raw)
        if "N/A" not in values:
            info = {
                "input_resolution": _tuple_get(values, 1),
                "input_color_schema": _tuple_get(values, 2),
                "input_color_depth": _tuple_get(values, 3),
                "output_resolution": _tuple_get(values, 5),
                "output_color_schema": _tuple_get(values, 6),
                "output_color_depth": _tuple_get(values, 7),
                "picture_mode": _tuple_get(values, 8),
            }
            self._attributes[ATTR_VIDEO_INFORMATION] = info
        else:
            self._attributes.pop(ATTR_VIDEO_INFORMATION, None)

    def _query_delayed_av_info(self):
        if not self._query_timer:
            self._query_timer = self.hass.loop.call_later(10, self._query_av_info)

    @callback
    def _query_av_info(self):
        self._query_avr("audio-information")
        self._query_avr("video-information")
        self._query_timer = None
