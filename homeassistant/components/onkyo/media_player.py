"""Media player platform."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aioonkyo import Code, Kind, Status, Zone, command, instruction, query, status

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OnkyoConfigEntry
from .const import (
    DOMAIN,
    LEGACY_HDMI_OUTPUT_MAPPING,
    LEGACY_REV_HDMI_OUTPUT_MAPPING,
    OPTION_MAX_VOLUME,
    OPTION_VOLUME_RESOLUTION,
    ZONES,
    InputSource,
    ListeningMode,
    VolumeResolution,
)
from .receiver import ReceiverManager
from .services import DATA_MP_ENTITIES
from .util import get_meaning

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OnkyoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MediaPlayer for config entry."""
    data = entry.runtime_data

    manager = data.manager
    all_entities = hass.data[DATA_MP_ENTITIES]

    entities: dict[Zone, OnkyoMediaPlayer] = {}
    all_entities[entry.entry_id] = entities

    volume_resolution: VolumeResolution = entry.options[OPTION_VOLUME_RESOLUTION]
    max_volume: float = entry.options[OPTION_MAX_VOLUME]
    sources = data.sources
    sound_modes = data.sound_modes

    async def connect_callback(reconnect: bool) -> None:
        if reconnect:
            for entity in entities.values():
                if entity.enabled:
                    await entity.backfill_state()

    async def update_callback(message: Status) -> None:
        if isinstance(message, status.Raw):
            return

        zone = message.zone

        entity = entities.get(zone)
        if entity is not None:
            if entity.enabled:
                entity.process_update(message)
        elif not isinstance(message, status.NotAvailable):
            # When we receive a valid status for a zone, then that zone is available on the receiver,
            # so we create the entity for it.
            _LOGGER.debug(
                "Discovered %s on %s (%s)",
                ZONES[zone],
                manager.info.model_name,
                manager.info.host,
            )
            zone_entity = OnkyoMediaPlayer(
                manager,
                zone,
                volume_resolution=volume_resolution,
                max_volume=max_volume,
                sources=sources,
                sound_modes=sound_modes,
            )
            entities[zone] = zone_entity
            async_add_entities([zone_entity])

    manager.callbacks.connect.append(connect_callback)
    manager.callbacks.update.append(update_callback)


class OnkyoMediaPlayer(MediaPlayerEntity):
    """Onkyo Receiver Media Player (one per each zone)."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    _supports_volume: bool = False
    # None means no technical possibility of support
    _supports_sound_mode: bool | None = None
    _supports_audio_info: bool = False
    _supports_video_info: bool = False

    _query_task: asyncio.Task | None = None

    def __init__(
        self,
        manager: ReceiverManager,
        zone: Zone,
        *,
        volume_resolution: VolumeResolution,
        max_volume: float,
        sources: dict[InputSource, str],
        sound_modes: dict[ListeningMode, str],
    ) -> None:
        """Initialize the Onkyo Receiver."""
        self._manager = manager
        self._zone = zone

        name = manager.info.model_name
        identifier = manager.info.identifier
        self._attr_name = f"{name}{' ' + ZONES[zone] if zone != Zone.MAIN else ''}"
        self._attr_unique_id = f"{identifier}_{zone.value}"

        self._volume_resolution = volume_resolution
        self._max_volume = max_volume

        zone_sources = InputSource.for_zone(zone)
        self._source_mapping = {
            key: value for key, value in sources.items() if key in zone_sources
        }
        self._rev_source_mapping = {
            value: key for key, value in self._source_mapping.items()
        }

        zone_sound_modes = ListeningMode.for_zone(zone)
        self._sound_mode_mapping = {
            key: value for key, value in sound_modes.items() if key in zone_sound_modes
        }
        self._rev_sound_mode_mapping = {
            value: key for key, value in self._sound_mode_mapping.items()
        }

        self._hdmi_output_mapping = LEGACY_HDMI_OUTPUT_MAPPING
        self._rev_hdmi_output_mapping = LEGACY_REV_HDMI_OUTPUT_MAPPING

        self._attr_source_list = list(self._rev_source_mapping)
        self._attr_sound_mode_list = list(self._rev_sound_mode_mapping)

        self._attr_supported_features = SUPPORTED_FEATURES_BASE
        if zone == Zone.MAIN:
            self._attr_supported_features |= SUPPORTED_FEATURES_VOLUME
            self._supports_volume = True
            self._attr_supported_features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE
            self._supports_sound_mode = True
        elif Code.get_from_kind_zone(Kind.LISTENING_MODE, zone) is not None:
            # To be detected later:
            self._supports_sound_mode = False

        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        """Entity has been added to hass."""
        await self.backfill_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the query timer when the entity is removed."""
        if self._query_task:
            self._query_task.cancel()
            self._query_task = None

    async def backfill_state(self) -> None:
        """Get the receiver to send all the info we care about.

        Usually run only on connect, as we can otherwise rely on the
        receiver to keep us informed of changes.
        """
        await self._manager.write(query.Power(self._zone))
        await self._manager.write(query.Volume(self._zone))
        await self._manager.write(query.Muting(self._zone))
        await self._manager.write(query.InputSource(self._zone))
        await self._manager.write(query.TunerPreset(self._zone))
        if self._supports_sound_mode is not None:
            await self._manager.write(query.ListeningMode(self._zone))
        if self._zone == Zone.MAIN:
            await self._manager.write(query.HDMIOutput())
            await self._manager.write(query.AudioInformation())
            await self._manager.write(query.VideoInformation())

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        message = command.Power(self._zone, command.Power.Param.ON)
        await self._manager.write(message)

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        message = command.Power(self._zone, command.Power.Param.STANDBY)
        await self._manager.write(message)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1.

        However full volume on the amp is usually far too loud so allow the user to
        specify the upper range with CONF_MAX_VOLUME. We change as per max_volume
        set by user. This means that if max volume is 80 then full volume in HA
        will give 80% volume on the receiver. Then we convert that to the correct
        scale for the receiver.
        """
        # HA_VOL * (MAX VOL / 100) * VOL_RESOLUTION
        value = round(volume * (self._max_volume / 100) * self._volume_resolution)
        message = command.Volume(self._zone, value)
        await self._manager.write(message)

    async def async_volume_up(self) -> None:
        """Increase volume by 1 step."""
        message = command.Volume(self._zone, command.Volume.Param.UP)
        await self._manager.write(message)

    async def async_volume_down(self) -> None:
        """Decrease volume by 1 step."""
        message = command.Volume(self._zone, command.Volume.Param.DOWN)
        await self._manager.write(message)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        message = command.Muting(
            self._zone, command.Muting.Param.ON if mute else command.Muting.Param.OFF
        )
        await self._manager.write(message)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if source not in self._rev_source_mapping:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={
                    "invalid_source": source,
                    "entity_id": self.entity_id,
                },
            )

        message = command.InputSource(self._zone, self._rev_source_mapping[source])
        await self._manager.write(message)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select listening sound mode."""
        if sound_mode not in self._rev_sound_mode_mapping:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_sound_mode",
                translation_placeholders={
                    "invalid_sound_mode": sound_mode,
                    "entity_id": self.entity_id,
                },
            )

        message = command.ListeningMode(
            self._zone, self._rev_sound_mode_mapping[sound_mode]
        )
        await self._manager.write(message)

    async def async_select_output(self, hdmi_output: str) -> None:
        """Set hdmi-out."""
        message = command.HDMIOutput(self._rev_hdmi_output_mapping[hdmi_output])
        await self._manager.write(message)

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play radio station by preset number."""
        if self.source is None:
            return

        source = self._rev_source_mapping.get(self.source)
        if media_type.lower() != "radio" or source not in PLAYABLE_SOURCES:
            return

        message = command.TunerPreset(self._zone, int(media_id))
        await self._manager.write(message)

    async def async_raw_command(self, rawCommand: str) -> None:
        """Send a raw eISCP command."""

        message = instruction.Raw(rawCommand.encode(), b"")
        await self._manager.write(message)

    def process_update(self, message: status.Known) -> None:
        """Process update."""
        match message:
            case status.Power(status.Power.Param.ON):
                self._attr_state = MediaPlayerState.ON
            case status.Power(status.Power.Param.STANDBY):
                self._attr_state = MediaPlayerState.OFF

            case status.Volume(volume):
                if not self._supports_volume:
                    self._attr_supported_features |= SUPPORTED_FEATURES_VOLUME
                    self._supports_volume = True
                # AMP_VOL / (VOL_RESOLUTION * (MAX_VOL / 100))
                volume_level: float = volume / (
                    self._volume_resolution * self._max_volume / 100
                )
                self._attr_volume_level = min(1, volume_level)

            case status.Muting(muting):
                self._attr_is_volume_muted = bool(muting == status.Muting.Param.ON)

            case status.InputSource(source):
                if source in self._source_mapping:
                    self._attr_source = self._source_mapping[source]
                else:
                    source_meaning = get_meaning(source)
                    _LOGGER.warning(
                        'Input source "%s" for entity: %s is not in the list. Check integration options',
                        source_meaning,
                        self.entity_id,
                    )
                    self._attr_source = source_meaning

                self._query_av_info_delayed()

            case status.ListeningMode(sound_mode):
                if not self._supports_sound_mode:
                    self._attr_supported_features |= (
                        MediaPlayerEntityFeature.SELECT_SOUND_MODE
                    )
                    self._supports_sound_mode = True

                if sound_mode in self._sound_mode_mapping:
                    self._attr_sound_mode = self._sound_mode_mapping[sound_mode]
                else:
                    sound_mode_meaning = get_meaning(sound_mode)
                    _LOGGER.warning(
                        'Listening mode "%s" for entity: %s is not in the list. Check integration options',
                        sound_mode_meaning,
                        self.entity_id,
                    )
                    self._attr_sound_mode = sound_mode_meaning

                self._query_av_info_delayed()

            case status.HDMIOutput(hdmi_output):
                self._attr_extra_state_attributes[ATTR_VIDEO_OUT] = (
                    self._hdmi_output_mapping[hdmi_output]
                )
                self._query_av_info_delayed()

            case status.TunerPreset(preset):
                self._attr_extra_state_attributes[ATTR_PRESET] = preset

            case status.AudioInformation():
                self._supports_audio_info = True
                audio_information = {}
                for item in AUDIO_INFORMATION_MAPPING:
                    item_value = getattr(message, item)
                    if item_value is not None:
                        audio_information[item] = item_value
                self._attr_extra_state_attributes[ATTR_AUDIO_INFORMATION] = (
                    audio_information
                )

            case status.VideoInformation():
                self._supports_video_info = True
                video_information = {}
                for item in VIDEO_INFORMATION_MAPPING:
                    item_value = getattr(message, item)
                    if item_value is not None:
                        video_information[item] = item_value
                self._attr_extra_state_attributes[ATTR_VIDEO_INFORMATION] = (
                    video_information
                )

            case status.FLDisplay():
                self._query_av_info_delayed()

            case status.NotAvailable(Kind.AUDIO_INFORMATION):
                # Not available right now, but still supported
                self._supports_audio_info = True

            case status.NotAvailable(Kind.VIDEO_INFORMATION):
                # Not available right now, but still supported
                self._supports_video_info = True

        self.async_write_ha_state()

    def _query_av_info_delayed(self) -> None:
        if self._zone == Zone.MAIN and not self._query_task:

            async def _query_av_info() -> None:
                await asyncio.sleep(AUDIO_VIDEO_INFORMATION_UPDATE_WAIT_TIME)
                if self._supports_audio_info:
                    await self._manager.write(query.AudioInformation())
                if self._supports_video_info:
                    await self._manager.write(query.VideoInformation())
                self._query_task = None

            self._query_task = asyncio.create_task(_query_av_info())
