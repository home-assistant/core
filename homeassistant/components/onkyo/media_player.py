"""Support for Onkyo Receivers."""

from __future__ import annotations

import asyncio
from enum import Enum
from functools import cache
import logging
from typing import Any, Literal

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OnkyoConfigEntry
from .const import (
    DOMAIN,
    OPTION_MAX_VOLUME,
    OPTION_VOLUME_RESOLUTION,
    PYEISCP_COMMANDS,
    ZONES,
    InputSource,
    ListeningMode,
    VolumeResolution,
)
from .receiver import Receiver
from .services import DATA_MP_ENTITIES

_LOGGER = logging.getLogger(__name__)


SUPPORTED_FEATURES_BASE = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY_MEDIA
)
SUPPORTED_FEATURES_VOLUME = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_STEP
)

PLAYABLE_SOURCES = (
    InputSource.FM,
    InputSource.AM,
    InputSource.DAB,
)

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
    "upmix_mode",
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
    "input_hdr",
]

type LibValue = str | tuple[str, ...]


def _get_single_lib_value(value: LibValue) -> str:
    if isinstance(value, str):
        return value
    return value[-1]


def _get_lib_mapping[T: Enum](cmds: Any, cls: type[T]) -> dict[T, LibValue]:
    result: dict[T, LibValue] = {}
    for k, v in cmds["values"].items():
        try:
            key = cls(k)
        except ValueError:
            continue
        result[key] = v["name"]

    return result


@cache
def _input_source_lib_mappings(zone: str) -> dict[InputSource, LibValue]:
    match zone:
        case "main":
            cmds = PYEISCP_COMMANDS["main"]["SLI"]
        case "zone2":
            cmds = PYEISCP_COMMANDS["zone2"]["SLZ"]
        case "zone3":
            cmds = PYEISCP_COMMANDS["zone3"]["SL3"]
        case "zone4":
            cmds = PYEISCP_COMMANDS["zone4"]["SL4"]

    return _get_lib_mapping(cmds, InputSource)


@cache
def _rev_input_source_lib_mappings(zone: str) -> dict[LibValue, InputSource]:
    return {value: key for key, value in _input_source_lib_mappings(zone).items()}


@cache
def _listening_mode_lib_mappings(zone: str) -> dict[ListeningMode, LibValue]:
    match zone:
        case "main":
            cmds = PYEISCP_COMMANDS["main"]["LMD"]
        case "zone2":
            cmds = PYEISCP_COMMANDS["zone2"]["LMZ"]
        case _:
            return {}

    return _get_lib_mapping(cmds, ListeningMode)


@cache
def _rev_listening_mode_lib_mappings(zone: str) -> dict[LibValue, ListeningMode]:
    return {value: key for key, value in _listening_mode_lib_mappings(zone).items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OnkyoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MediaPlayer for config entry."""
    data = entry.runtime_data

    receiver = data.receiver
    all_entities = hass.data[DATA_MP_ENTITIES]

    entities: dict[str, OnkyoMediaPlayer] = {}
    all_entities[entry.entry_id] = entities

    volume_resolution: VolumeResolution = entry.options[OPTION_VOLUME_RESOLUTION]
    max_volume: float = entry.options[OPTION_MAX_VOLUME]
    sources = data.sources
    sound_modes = data.sound_modes

    def connect_callback(receiver: Receiver) -> None:
        if not receiver.first_connect:
            for entity in entities.values():
                if entity.enabled:
                    entity.backfill_state()

    def update_callback(receiver: Receiver, message: tuple[str, str, Any]) -> None:
        zone, _, value = message
        entity = entities.get(zone)
        if entity is not None:
            if entity.enabled:
                entity.process_update(message)
        elif zone in ZONES and value != "N/A":
            # When we receive the status for a zone, and the value is not "N/A",
            # then zone is available on the receiver, so we create the entity for it.
            _LOGGER.debug(
                "Discovered %s on %s (%s)",
                ZONES[zone],
                receiver.model_name,
                receiver.host,
            )
            zone_entity = OnkyoMediaPlayer(
                receiver,
                zone,
                volume_resolution=volume_resolution,
                max_volume=max_volume,
                sources=sources,
                sound_modes=sound_modes,
            )
            entities[zone] = zone_entity
            async_add_entities([zone_entity])

    receiver.callbacks.connect.append(connect_callback)
    receiver.callbacks.update.append(update_callback)


class OnkyoMediaPlayer(MediaPlayerEntity):
    """Representation of an Onkyo Receiver Media Player (one per each zone)."""

    _attr_should_poll = False

    _supports_volume: bool = False
    _supports_sound_mode: bool = False
    _supports_audio_info: bool = False
    _supports_video_info: bool = False
    _query_timer: asyncio.TimerHandle | None = None

    def __init__(
        self,
        receiver: Receiver,
        zone: str,
        *,
        volume_resolution: VolumeResolution,
        max_volume: float,
        sources: dict[InputSource, str],
        sound_modes: dict[ListeningMode, str],
    ) -> None:
        """Initialize the Onkyo Receiver."""
        self._receiver = receiver
        name = receiver.model_name
        identifier = receiver.identifier
        self._attr_name = f"{name}{' ' + ZONES[zone] if zone != 'main' else ''}"
        self._attr_unique_id = f"{identifier}_{zone}"

        self._zone = zone

        self._volume_resolution = volume_resolution
        self._max_volume = max_volume

        self._options_sources = sources
        self._source_lib_mapping = _input_source_lib_mappings(zone)
        self._rev_source_lib_mapping = _rev_input_source_lib_mappings(zone)
        self._source_mapping = {
            key: value
            for key, value in sources.items()
            if key in self._source_lib_mapping
        }
        self._rev_source_mapping = {
            value: key for key, value in self._source_mapping.items()
        }

        self._options_sound_modes = sound_modes
        self._sound_mode_lib_mapping = _listening_mode_lib_mappings(zone)
        self._rev_sound_mode_lib_mapping = _rev_listening_mode_lib_mappings(zone)
        self._sound_mode_mapping = {
            key: value
            for key, value in sound_modes.items()
            if key in self._sound_mode_lib_mapping
        }
        self._rev_sound_mode_mapping = {
            value: key for key, value in self._sound_mode_mapping.items()
        }

        self._attr_source_list = list(self._rev_source_mapping)
        self._attr_sound_mode_list = list(self._rev_sound_mode_mapping)

        self._attr_supported_features = SUPPORTED_FEATURES_BASE
        if zone == "main":
            self._attr_supported_features |= SUPPORTED_FEATURES_VOLUME
            self._supports_volume = True
            self._attr_supported_features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE
            self._supports_sound_mode = True

        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        """Entity has been added to hass."""
        self.backfill_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the query timer when the entity is removed."""
        if self._query_timer:
            self._query_timer.cancel()
            self._query_timer = None

    @callback
    def _update_receiver(self, propname: str, value: Any) -> None:
        """Update a property in the receiver."""
        self._receiver.conn.update_property(self._zone, propname, value)

    @callback
    def _query_receiver(self, propname: str) -> None:
        """Cause the receiver to send an update about a property."""
        self._receiver.conn.query_property(self._zone, propname)

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
        # HA_VOL * (MAX VOL / 100) * VOL_RESOLUTION
        self._update_receiver(
            "volume", round(volume * (self._max_volume / 100) * self._volume_resolution)
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
        if not self.source_list or source not in self.source_list:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={
                    "invalid_source": source,
                    "entity_id": self.entity_id,
                },
            )

        source_lib = self._source_lib_mapping[self._rev_source_mapping[source]]
        source_lib_single = _get_single_lib_value(source_lib)
        self._update_receiver(
            "input-selector" if self._zone == "main" else "selector", source_lib_single
        )

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select listening sound mode."""
        if not self.sound_mode_list or sound_mode not in self.sound_mode_list:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_sound_mode",
                translation_placeholders={
                    "invalid_sound_mode": sound_mode,
                    "entity_id": self.entity_id,
                },
            )

        sound_mode_lib = self._sound_mode_lib_mapping[
            self._rev_sound_mode_mapping[sound_mode]
        ]
        sound_mode_lib_single = _get_single_lib_value(sound_mode_lib)
        self._update_receiver("listening-mode", sound_mode_lib_single)

    async def async_select_output(self, hdmi_output: str) -> None:
        """Set hdmi-out."""
        self._update_receiver("hdmi-output-selector", hdmi_output)

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play radio station by preset number."""
        if self.source is not None:
            source = self._rev_source_mapping[self.source]
            if media_type.lower() == "radio" and source in PLAYABLE_SOURCES:
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
            if not self._supports_volume:
                self._attr_supported_features |= SUPPORTED_FEATURES_VOLUME
                self._supports_volume = True
            # AMP_VOL / (VOL_RESOLUTION * (MAX_VOL / 100))
            volume_level: float = value / (
                self._volume_resolution * self._max_volume / 100
            )
            self._attr_volume_level = min(1, volume_level)
        elif command in ["muting", "audio-muting"]:
            self._attr_is_volume_muted = bool(value == "on")
        elif command in ["selector", "input-selector"] and value != "N/A":
            self._parse_source(value)
            self._query_av_info_delayed()
        elif command == "hdmi-output-selector":
            self._attr_extra_state_attributes[ATTR_VIDEO_OUT] = ",".join(value)
        elif command == "preset":
            if self.source is not None and self.source.lower() == "radio":
                self._attr_extra_state_attributes[ATTR_PRESET] = value
            elif ATTR_PRESET in self._attr_extra_state_attributes:
                del self._attr_extra_state_attributes[ATTR_PRESET]
        elif command == "listening-mode" and value != "N/A":
            if not self._supports_sound_mode:
                self._attr_supported_features |= (
                    MediaPlayerEntityFeature.SELECT_SOUND_MODE
                )
                self._supports_sound_mode = True
            self._parse_sound_mode(value)
            self._query_av_info_delayed()
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
    def _parse_source(self, source_lib: LibValue) -> None:
        source = self._rev_source_lib_mapping[source_lib]
        if source in self._source_mapping:
            self._attr_source = self._source_mapping[source]
            return

        source_meaning = source.value_meaning

        if source not in self._options_sources:
            _LOGGER.warning(
                'Input source "%s" for entity: %s is not in the list. Check integration options',
                source_meaning,
                self.entity_id,
            )
        else:
            _LOGGER.error(
                'Input source "%s" is invalid for entity: %s',
                source_meaning,
                self.entity_id,
            )

        self._attr_source = source_meaning

    @callback
    def _parse_sound_mode(self, mode_lib: LibValue) -> None:
        sound_mode = self._rev_sound_mode_lib_mapping[mode_lib]
        if sound_mode in self._sound_mode_mapping:
            self._attr_sound_mode = self._sound_mode_mapping[sound_mode]
            return

        sound_mode_meaning = sound_mode.value_meaning

        if sound_mode not in self._options_sound_modes:
            _LOGGER.warning(
                'Listening mode "%s" for entity: %s is not in the list. Check integration options',
                sound_mode_meaning,
                self.entity_id,
            )
        else:
            _LOGGER.error(
                'Listening mode "%s" is invalid for entity: %s',
                sound_mode_meaning,
                self.entity_id,
            )

        self._attr_sound_mode = sound_mode_meaning

    @callback
    def _parse_audio_information(
        self, audio_information: tuple[str] | Literal["N/A"]
    ) -> None:
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
    def _parse_video_information(
        self, video_information: tuple[str] | Literal["N/A"]
    ) -> None:
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

    def _query_av_info_delayed(self) -> None:
        if self._zone == "main" and not self._query_timer:

            @callback
            def _query_av_info() -> None:
                if self._supports_audio_info:
                    self._query_receiver("audio-information")
                if self._supports_video_info:
                    self._query_receiver("video-information")
                self._query_timer = None

            self._query_timer = self.hass.loop.call_later(
                AUDIO_VIDEO_INFORMATION_UPDATE_WAIT_TIME, _query_av_info
            )
