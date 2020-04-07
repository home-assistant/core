#!/usr/bin/python3
"""Support for Onkyo Network Receivers and Processors."""
import logging

import pyeiscp
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
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
)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "onkyo"

DEFAULT_PORT = 60128

CONF_SOURCES = "sources"
CONF_MAX_VOLUME = "max_volume"
CONF_RECEIVER_MAX_VOLUME = "receiver_max_volume"
CONF_ZONES = "zones"

DEFAULT_NAME = "Onkyo Receiver"
SUPPORTED_MAX_VOLUME = 90
DEFAULT_RECEIVER_MAX_VOLUME = 90
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

DEFAULT_PLAYABLE_SOURCES = ("fm", "am", "tuner")

SUPPORT_ONKYO = (
    SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
)

SUPPORT_ONKYO_WO_VOLUME = (
    SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_MAX_VOLUME, default=SUPPORTED_MAX_VOLUME): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Optional(
            CONF_RECEIVER_MAX_VOLUME, default=DEFAULT_RECEIVER_MAX_VOLUME
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional(CONF_SOURCES, default=DEFAULT_SOURCES): {cv.string: cv.string},
        vol.Optional(CONF_ZONES, default=[]): vol.All(cv.ensure_list, [vol.In(ZONES)]),
    }
)

ATTR_HDMI_OUTPUT = "hdmi_output"
ATTR_PRESET = "preset"

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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up our socket to the AVR."""

    host = config[CONF_HOST]
    port = config[CONF_PORT]
    name = config[CONF_NAME] or "Onkyo Receiver"
    max_volume = config[CONF_MAX_VOLUME]
    receiver_max_volume = config[CONF_RECEIVER_MAX_VOLUME]
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
        active_zones[zone] = OnkyoAVR(
            avr, name, sources, zone, max_volume, receiver_max_volume
        )

    for zone in active_zones.values():
        zone.backfill_state()
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, zone.avr.close)

    async_add_entities(active_zones.values())


class OnkyoAVR(MediaPlayerDevice):
    """Entity reading values from Onkyo AVR protocol."""

    def __init__(self, avr, name, sources, zone, max_volume, receiver_max_volume):
        """Initialize entity with transport."""
        super().__init__()
        self.avr = avr
        self._name = f"{name} {zone if zone != 'main' else ''}"
        self._zone = zone
        self._volume = 0
        self._supports_volume = False
        self._muted = False
        self._max_volume = max_volume
        self._receiver_max_volume = receiver_max_volume
        self._powerstate = STATE_ON
        self._source = None
        self._source_list = list(sources.values())
        self._source_mapping = sources
        self._reverse_mapping = {value: key for key, value in sources.items()}
        self._attributes = {}

    def process_update(self, update):
        """Store relevant updates so they can be queried later."""
        _, command, value = update
        if command in ["system-power", "power"]:
            if value == "on":
                self._powerstate = STATE_ON
            else:
                self._powerstate = STATE_OFF
        elif command in ["volume", "master-volume"]:
            self._supports_volume = True
            self._volume = value / self._receiver_max_volume * (self._max_volume / 100)
        elif command == "audio-muting":
            self._muted = bool(value == "on")
        elif command == "input-selector":
            # eiscp can return string or tuple. Make everything tuples.
            if isinstance(value, str):
                current_source_tuples = (command, (value,))
            else:
                current_source_tuples = (command, value)

            for source in current_source_tuples[1]:
                if source in self._source_mapping:
                    self._source = self._source_mapping[source]
                    break
                self._source = "_".join(current_source_tuples[1])
        elif command == "hdmi-output-selector":
            self._attributes["video_out"] = ",".join(value)
        elif command == "preset":
            if not (self._source is None) and self._source.lower() == "radio":
                self._attributes[ATTR_PRESET] = value
            elif ATTR_PRESET in self._attributes:
                del self._attributes[ATTR_PRESET]

    def backfill_state(self):
        """Get the receiver to send all the info we care about.

        Usually run only on connect, as we can otherwise rely on the
        receiver to keep us informed of changes.
        """
        self._query_avr("power")
        self._query_avr("volume")
        self._query_avr("input-selector")
        self._query_avr("preset")
        if self._zone == "main":
            self._query_avr("hdmi-output-selector")
            self._query_avr("audio-muting")

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._supports_volume:
            return SUPPORT_ONKYO
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

    async def async_select_source(self, source):
        """Change AVR to the designated source (by name)."""
        if source in self._source_list:
            source = self._reverse_mapping[source]
        self._update_avr("input_name", source)

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
        self._update_avr(
            "volume", int(volume * (self._max_volume / 100) * self._receiver_max_volume)
        )

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
