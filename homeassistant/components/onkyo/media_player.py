"""Support for Onkyo Receivers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pyeiscp
import voluptuous as vol

from homeassistant.components.media_player import (
    DOMAIN,
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_SOURCES = "sources"
CONF_MAX_VOLUME = "max_volume"
CONF_RECEIVER_MAX_VOLUME = "receiver_max_volume"

DEFAULT_NAME = "Onkyo Receiver"
SUPPORTED_MAX_VOLUME = 100
DEFAULT_RECEIVER_MAX_VOLUME = 80
ZONES = {"zone2": "Zone 2", "zone3": "Zone 3", "zone4": "Zone 4"}

SUPPORT_ONKYO_WO_VOLUME = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY_MEDIA
)
SUPPORT_ONKYO = (
    SUPPORT_ONKYO_WO_VOLUME
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_STEP
)

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
DEFAULT_PLAYABLE_SOURCES = ("fm", "am", "tuner")

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MAX_VOLUME, default=SUPPORTED_MAX_VOLUME): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Optional(
            CONF_RECEIVER_MAX_VOLUME, default=DEFAULT_RECEIVER_MAX_VOLUME
        ): cv.positive_int,
        vol.Optional(CONF_SOURCES, default=DEFAULT_SOURCES): {cv.string: cv.string},
    }
)

ATTR_HDMI_OUTPUT = "hdmi_output"
ATTR_PRESET = "preset"
ATTR_AUDIO_INFORMATION = "audio_information"
ATTR_VIDEO_INFORMATION = "video_information"
ATTR_VIDEO_OUT = "video_out"

AUDIO_VIDEO_INFORMATION_UPDATE_WAIT_TIME = 8

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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Onkyo platform."""
    receivers: dict[str, pyeiscp.Connection] = {}  # indexed by host
    entities: dict[str, dict[str, OnkyoMediaPlayer]] = {}  # indexed by host and zone

    async def async_service_handle(service: ServiceCall) -> None:
        """Handle for services."""
        entity_ids = service.data[ATTR_ENTITY_ID]
        targets = [
            entity
            for h in entities.values()
            for entity in h.values()
            if entity.entity_id in entity_ids
        ]

        for target in targets:
            if service.service == SERVICE_SELECT_HDMI_OUTPUT:
                await target.async_select_output(service.data[ATTR_HDMI_OUTPUT])

    hass.services.async_register(
        DOMAIN,
        SERVICE_SELECT_HDMI_OUTPUT,
        async_service_handle,
        schema=ONKYO_SELECT_OUTPUT_SCHEMA,
    )

    host = config.get(CONF_HOST)
    name = config[CONF_NAME]
    max_volume = config[CONF_MAX_VOLUME]
    receiver_max_volume = config[CONF_RECEIVER_MAX_VOLUME]
    sources = config[CONF_SOURCES]

    @callback
    def async_onkyo_update_callback(message: tuple[str, str, Any], origin: str) -> None:
        """Process new message from receiver."""
        receiver = receivers[origin]
        _LOGGER.debug("Received update callback from %s: %s", receiver.name, message)

        zone, _, value = message
        entity = entities[origin].get(zone)
        if entity is not None:
            if entity.enabled:
                entity.process_update(message)
        elif zone in ZONES and value != "N/A":
            # When we receive the status for a zone, and the value is not "N/A",
            # then zone is available on the receiver, so we create the entity for it.
            _LOGGER.debug("Discovered %s on %s", ZONES[zone], receiver.name)
            zone_entity = OnkyoMediaPlayer(
                receiver, sources, zone, max_volume, receiver_max_volume
            )
            entities[origin][zone] = zone_entity
            async_add_entities([zone_entity])

    @callback
    def async_onkyo_connect_callback(origin: str) -> None:
        """Receiver (re)connected."""
        receiver = receivers[origin]
        _LOGGER.debug("Receiver (re)connected: %s (%s)", receiver.name, receiver.host)

        for entity in entities[origin].values():
            entity.backfill_state()

    def setup_receiver(receiver: pyeiscp.Connection) -> None:
        KNOWN_HOSTS.append(receiver.host)

        # Store the receiver object and create a dictionary to store its entities.
        receivers[receiver.host] = receiver
        entities[receiver.host] = {}

        # Discover what zones are available for the receiver by querying the power.
        # If we get a response for the specific zone, it means it is available.
        for zone in ZONES:
            receiver.query_property(zone, "power")

        # Add the main zone to entities, since it is always active.
        _LOGGER.debug("Adding Main Zone on %s", receiver.name)
        main_entity = OnkyoMediaPlayer(
            receiver, sources, "main", max_volume, receiver_max_volume
        )
        entities[receiver.host]["main"] = main_entity
        async_add_entities([main_entity])

    if host is not None and host not in KNOWN_HOSTS:
        _LOGGER.debug("Manually creating receiver: %s (%s)", name, host)
        receiver = await pyeiscp.Connection.create(
            host=host,
            update_callback=async_onkyo_update_callback,
            connect_callback=async_onkyo_connect_callback,
        )

        # The library automatically adds a name and identifier only on discovered hosts,
        # so manually add them here instead.
        receiver.name = name
        receiver.identifier = None

        setup_receiver(receiver)
    else:

        @callback
        async def async_onkyo_discovery_callback(receiver: pyeiscp.Connection):
            """Receiver discovered, connection not yet active."""
            _LOGGER.debug("Receiver discovered: %s (%s)", receiver.name, receiver.host)
            if receiver.host not in KNOWN_HOSTS:
                await receiver.connect()
                setup_receiver(receiver)

        _LOGGER.debug("Discovering receivers")
        await pyeiscp.Connection.discover(
            update_callback=async_onkyo_update_callback,
            connect_callback=async_onkyo_connect_callback,
            discovery_callback=async_onkyo_discovery_callback,
        )

    @callback
    def close_receiver(_event):
        for receiver in receivers.values():
            receiver.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_receiver)


class OnkyoMediaPlayer(MediaPlayerEntity):
    """Representation of an Onkyo Receiver Media Player (one per each zone)."""

    _attr_should_poll = False

    _supports_volume: bool = False
    _supports_audio_info: bool = False
    _supports_video_info: bool = False
    _query_timer: asyncio.TimerHandle | None = None

    def __init__(
        self,
        receiver: pyeiscp.Connection,
        sources: dict[str, str],
        zone: str,
        max_volume: int,
        receiver_max_volume: int,
    ) -> None:
        """Initialize the Onkyo Receiver."""
        self._receiver = receiver
        name = receiver.name
        self._attr_name = f"{name}{' ' + ZONES[zone] if zone != 'main' else ''}"
        identifier = receiver.identifier
        if identifier is not None:
            # discovered
            if zone == "main":
                # keep legacy unique_id
                self._attr_unique_id = f"{name}_{identifier}"
            else:
                self._attr_unique_id = f"{identifier}_{zone}"
        else:
            # not discovered
            self._attr_unique_id = None

        self._zone = zone
        self._source_mapping = sources
        self._reverse_mapping = {value: key for key, value in sources.items()}
        self._max_volume = max_volume
        self._receiver_max_volume = receiver_max_volume

        self._attr_source_list = list(sources.values())
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        """Entity has been added to hass."""
        self.backfill_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the query timer when the entity is removed."""
        if self._query_timer:
            self._query_timer.cancel()
            self._query_timer = None

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return media player features that are supported."""
        if self._supports_volume:
            return SUPPORT_ONKYO
        return SUPPORT_ONKYO_WO_VOLUME

    @callback
    def _update_receiver(self, propname: str, value: Any) -> None:
        """Update a property in the receiver."""
        self._receiver.update_property(self._zone, propname, value)

    @callback
    def _query_receiver(self, propname: str) -> None:
        """Cause the receiver to send an update about a property."""
        self._receiver.query_property(self._zone, propname)

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        self._update_receiver("power", "on")

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        self._update_receiver("power", "standby")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1.

        However full volume on the amp is usually far too loud so allow the user to
        specify the upper range with CONF_MAX_VOLUME. We change as per max_volume
        set by user. This means that if max volume is 80 then full volume in HA
        will give 80% volume on the receiver. Then we convert that to the correct
        scale for the receiver.
        """
        # HA_VOL * (MAX VOL / 100) * MAX_RECEIVER_VOL
        self._update_receiver(
            "volume", int(volume * (self._max_volume / 100) * self._receiver_max_volume)
        )

    async def async_volume_up(self) -> None:
        """Increase volume by 1 step."""
        self._update_receiver("volume", "level-up")

    async def async_volume_down(self) -> None:
        """Decrease volume by 1 step."""
        self._update_receiver("volume", "level-down")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        self._update_receiver(
            "audio-muting" if self._zone == "main" else "muting",
            "on" if mute else "off",
        )

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if self.source_list and source in self.source_list:
            source = self._reverse_mapping[source]
        self._update_receiver(
            "input-selector" if self._zone == "main" else "selector", source
        )

    async def async_select_output(self, hdmi_output: str) -> None:
        """Set hdmi-out."""
        self._update_receiver("hdmi-output-selector", hdmi_output)

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play radio station by preset number."""
        if self.source is not None:
            source = self._reverse_mapping[self.source]
            if media_type.lower() == "radio" and source in DEFAULT_PLAYABLE_SOURCES:
                self._update_receiver("preset", media_id)

    @callback
    def backfill_state(self) -> None:
        """Get the receiver to send all the info we care about.

        Usually run only on connect, as we can otherwise rely on the
        receiver to keep us informed of changes.
        """
        self._query_receiver("power")
        self._query_receiver("volume")
        self._query_receiver("preset")
        if self._zone == "main":
            self._query_receiver("hdmi-output-selector")
            self._query_receiver("audio-muting")
            self._query_receiver("input-selector")
            self._query_receiver("listening-mode")
            self._query_receiver("audio-information")
            self._query_receiver("video-information")
        else:
            self._query_receiver("muting")
            self._query_receiver("selector")

    @callback
    def process_update(self, update: tuple[str, str, Any]) -> None:
        """Store relevant updates so they can be queried later."""
        zone, command, value = update
        if zone != self._zone:
            return

        if command in ["system-power", "power"]:
            if value == "on":
                self._attr_state = MediaPlayerState.ON
            else:
                self._attr_state = MediaPlayerState.OFF
                self._attr_extra_state_attributes.pop(ATTR_AUDIO_INFORMATION, None)
                self._attr_extra_state_attributes.pop(ATTR_VIDEO_INFORMATION, None)
                self._attr_extra_state_attributes.pop(ATTR_PRESET, None)
                self._attr_extra_state_attributes.pop(ATTR_VIDEO_OUT, None)
        elif command in ["volume", "master-volume"] and value != "N/A":
            self._supports_volume = True
            # AMP_VOL / (MAX_RECEIVER_VOL * (MAX_VOL / 100))
            self._attr_volume_level = value / (
                self._receiver_max_volume * self._max_volume / 100
            )
        elif command in ["muting", "audio-muting"]:
            self._attr_is_volume_muted = bool(value == "on")
        elif command in ["selector", "input-selector"]:
            self._parse_source(value)
            self._query_av_info_delayed()
        elif command == "hdmi-output-selector":
            self._attr_extra_state_attributes[ATTR_VIDEO_OUT] = ",".join(value)
        elif command == "preset":
            if self.source is not None and self.source.lower() == "radio":
                self._attr_extra_state_attributes[ATTR_PRESET] = value
            elif ATTR_PRESET in self._attr_extra_state_attributes:
                del self._attr_extra_state_attributes[ATTR_PRESET]
        elif command == "audio-information":
            self._supports_audio_info = True
            self._parse_audio_information(value)
        elif command == "video-information":
            self._supports_video_info = True
            self._parse_video_information(value)
        elif command == "fl-display-information":
            self._query_av_info_delayed()

        self.async_write_ha_state()

    @callback
    def _parse_source(self, source):
        # source is either a tuple of values or a single value,
        # so we convert to a tuple, when it is a single value.
        if not isinstance(source, tuple):
            source = (source,)
        for value in source:
            if value in self._source_mapping:
                self._attr_source = self._source_mapping[value]
                break
            self._attr_source = "_".join(source)

    @callback
    def _parse_audio_information(self, audio_information):
        # If audio information is not available, N/A is returned,
        # so only update the audio information, when it is not N/A.
        if audio_information == "N/A":
            self._attr_extra_state_attributes.pop(ATTR_AUDIO_INFORMATION, None)
            return

        self._attr_extra_state_attributes[ATTR_AUDIO_INFORMATION] = {
            name: value
            for name, value in zip(
                AUDIO_INFORMATION_MAPPING, audio_information, strict=False
            )
            if len(value) > 0
        }

    @callback
    def _parse_video_information(self, video_information):
        # If video information is not available, N/A is returned,
        # so only update the video information, when it is not N/A.
        if video_information == "N/A":
            self._attr_extra_state_attributes.pop(ATTR_VIDEO_INFORMATION, None)
            return

        self._attr_extra_state_attributes[ATTR_VIDEO_INFORMATION] = {
            name: value
            for name, value in zip(
                VIDEO_INFORMATION_MAPPING, video_information, strict=False
            )
            if len(value) > 0
        }

    def _query_av_info_delayed(self):
        if self._zone == "main" and not self._query_timer:

            @callback
            def _query_av_info():
                if self._supports_audio_info:
                    self._query_receiver("audio-information")
                if self._supports_video_info:
                    self._query_receiver("video-information")
                self._query_timer = None

            self._query_timer = self.hass.loop.call_later(
                AUDIO_VIDEO_INFORMATION_UPDATE_WAIT_TIME, _query_av_info
            )
