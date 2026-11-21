"""Media player platform."""

import asyncio
from datetime import datetime
import hashlib
import logging
from typing import TYPE_CHECKING, Any, override

import aiohttp
from aioonkyo import (
    Code,
    Kind,
    NetArtType,
    NetPlaybackState,
    Status,
    Zone,
    command,
    query,
    status,
)

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

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
from .util import get_meaning

if TYPE_CHECKING:
    from . import OnkyoConfigEntry

_LOGGER = logging.getLogger(__name__)


DATA_MP_ENTITIES: HassKey[dict[str, dict[Zone, OnkyoMediaPlayer]]] = HassKey(DOMAIN)


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

SUPPORTED_FEATURES_NET = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
)

PLAYABLE_SOURCES = (
    InputSource.FM,
    InputSource.AM,
    InputSource.DAB,
)

# Inputs played by the receiver's NET/USB player
NET_SOURCES = (
    InputSource.MUSIC_SERVER_P4S_DLNA,
    InputSource.INTERNET_RADIO,
    InputSource.USB,
    InputSource.USB_REAR,
    InputSource.NETWORK,
    InputSource.AIRPLAY,
    InputSource.BLUETOOTH,
)

NET_PLAYBACK_STATES = {
    NetPlaybackState.PLAYING: MediaPlayerState.PLAYING,
    NetPlaybackState.FAST_FORWARD: MediaPlayerState.PLAYING,
    NetPlaybackState.FAST_REVERSE: MediaPlayerState.PLAYING,
    NetPlaybackState.PAUSED: MediaPlayerState.PAUSED,
    NetPlaybackState.STOPPED: MediaPlayerState.IDLE,
    NetPlaybackState.END: MediaPlayerState.IDLE,
}

ATTR_PRESET = "preset"
ATTR_AUDIO_INFORMATION = "audio_information"
ATTR_VIDEO_INFORMATION = "video_information"
ATTR_VIDEO_OUT = "video_out"

QUERY_STATE_DELAY = 4
QUERY_AV_INFO_DELAY = 8
QUERY_NET_DELAY = 1

# The receiver reports the position every second while playing. Only a jump
# this large (in seconds) from the expected position is written to the state.
NET_POSITION_TOLERANCE = 2

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
    """Set up media player platform for config entry."""
    data = entry.runtime_data

    manager = data.manager
    all_entities = hass.data[DATA_MP_ENTITIES]

    entities: dict[Zone, OnkyoMediaPlayer] = {}
    all_entities[entry.entry_id] = entities

    @callback
    def del_mp_entities() -> None:
        del all_entities[entry.entry_id]

    entry.async_on_unload(del_mp_entities)

    volume_resolution: VolumeResolution = entry.options[OPTION_VOLUME_RESOLUTION]
    max_volume: float = entry.options[OPTION_MAX_VOLUME]
    sources = data.sources
    sound_modes = data.sound_modes

    async def connect_callback(reconnect: bool) -> None:
        if reconnect:
            for entity in entities.values():
                if entity.enabled:
                    await entity.query_state()

    async def disconnect_callback() -> None:
        for entity in entities.values():
            if entity.enabled:
                entity.cancel_pending()
                entity.clear_net_playback()
                entity.async_write_ha_state()

    async def update_callback(message: Status) -> None:
        if isinstance(message, status.Raw):
            return

        zone = message.zone

        entity = entities.get(zone)
        if entity is not None:
            if entity.enabled:
                entity.process_update(message)
        elif not isinstance(message, status.NotAvailable):
            # When we receive a valid status for a zone, then
            # that zone is available on the receiver,
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
    manager.callbacks.disconnect.append(disconnect_callback)
    manager.callbacks.update.append(update_callback)


class OnkyoMediaPlayer(MediaPlayerEntity):
    """Onkyo Receiver Media Player (one per each zone)."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_should_poll = False
    _attr_has_entity_name = True

    _supports_volume: bool = False
    # None means no technical possibility of support
    _supports_sound_mode: bool | None = None
    _supports_audio_info: bool = False
    _supports_video_info: bool = False

    _query_state_unsub: CALLBACK_TYPE | None = None
    _query_av_info_unsub: CALLBACK_TYPE | None = None
    _query_net_unsub: CALLBACK_TYPE | None = None

    # The selected input, while it is one played by the NET/USB player
    _net_input: InputSource | None = None
    _net_state: MediaPlayerState | None = None

    # Cover art: the receiver reports an address on itself. It serves the same
    # address for every track, so the image hash is built from the track and a
    # counter that grows with every art report.
    _net_art_url: str | None = None
    _net_art_serial: int = 0

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
        self._attr_name = f"{name}{' ' + ZONES[zone] if zone is not Zone.MAIN else ''}"
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
        if zone is Zone.MAIN:
            self._attr_supported_features |= SUPPORTED_FEATURES_VOLUME
            self._supports_volume = True
            self._attr_supported_features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE
            self._supports_sound_mode = True
        elif Code.get_from_kind_zone(Kind.LISTENING_MODE, zone) is not None:
            # To be detected later:
            self._supports_sound_mode = False

        self._attr_extra_state_attributes = {}

    @override
    async def async_added_to_hass(self) -> None:
        """Entity has been added to hass."""
        await self.query_state()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Entity will be removed from hass."""
        self.cancel_pending()

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return self._manager.connected

    @property
    @override
    def state(self) -> MediaPlayerState | None:
        """Return the playback state while the NET/USB player reports one."""
        if self._attr_state is MediaPlayerState.ON and self._net_state is not None:
            return self._net_state
        return self._attr_state

    @property
    @override
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Add transport controls while the NET/USB player reports a state."""
        if self._attr_state is MediaPlayerState.ON and self._net_state is not None:
            return self._attr_supported_features | SUPPORTED_FEATURES_NET
        return self._attr_supported_features

    async def query_state(self) -> None:
        """Query the receiver for all the info, that we care about."""
        await self._manager.write(query.Power(self._zone))
        await self._manager.write(query.Volume(self._zone))
        await self._manager.write(query.Muting(self._zone))
        await self._manager.write(query.InputSource(self._zone))
        await self._manager.write(query.TunerPreset(self._zone))
        if self._supports_sound_mode is not None:
            await self._manager.write(query.ListeningMode(self._zone))
        if self._zone is Zone.MAIN:
            await self._manager.write(query.HDMIOutput())
            await self._manager.write(query.AudioInformation())
            await self._manager.write(query.VideoInformation())

    def cancel_pending(self) -> None:
        """Cancel the pending work."""
        if self._query_state_unsub is not None:
            self._query_state_unsub()
            self._query_state_unsub = None
        if self._query_av_info_unsub is not None:
            self._query_av_info_unsub()
            self._query_av_info_unsub = None
        if self._query_net_unsub is not None:
            self._query_net_unsub()
            self._query_net_unsub = None

    def clear_net_playback(self) -> None:
        """Forget the NET/USB player state."""
        self._net_input = None
        self._net_state = None
        self._attr_media_content_type = None
        self._attr_media_title = None
        self._attr_media_artist = None
        self._attr_media_album_name = None
        self._attr_media_track = None
        self._attr_media_duration = None
        self._attr_media_position = None
        self._attr_media_position_updated_at = None
        self._net_art_url = None

    @property
    @override
    def media_image_url(self) -> str | None:
        """Return the cover art address while the NET/USB player reports a state."""
        if self._attr_state is MediaPlayerState.ON and self._net_state is not None:
            return self._net_art_url
        return None

    @property
    @override
    def media_image_hash(self) -> str | None:
        """Return a hash that changes with the track, so Home Assistant reloads the art."""
        if (url := self.media_image_url) is None:
            return None
        key = "|".join(
            (
                url,
                str(self._net_art_serial),
                self._attr_media_title or "",
                self._attr_media_artist or "",
                self._attr_media_album_name or "",
            )
        )
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    @override
    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Fetch the cover art from the receiver.

        These receivers answer with a few header-like lines in front of the image
        ("Content-size: 129128", "Content-type: image/jpeg", empty line), so they are
        removed here to leave a plain image.
        """
        if (url := self.media_image_url) is None:
            return None, None
        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(10):
                response = await session.get(url)
                response.raise_for_status()
                body = await response.read()
        except (aiohttp.ClientError, TimeoutError):
            return None, None
        content_type = response.content_type
        if body[:13].lower() == b"content-size:":
            # Read the header lines up to the empty one, with LF or CRLF endings
            rest = body
            while True:
                line, found, rest = rest.partition(b"\n")
                if not found:
                    return None, None
                line = line.rstrip(b"\r")
                if not line:
                    break
                name, _, value = line.partition(b":")
                if name.strip().lower() == b"content-type":
                    content_type = value.strip().decode("ascii", "replace")
            body = rest
        return body, content_type

    @override
    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        message = command.Power(self._zone, command.Power.Param.ON)
        await self._manager.write(message)

    @override
    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        message = command.Power(self._zone, command.Power.Param.STANDBY)
        await self._manager.write(message)

    @override
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

    @override
    async def async_volume_up(self) -> None:
        """Increase volume by 1 step."""
        message = command.Volume(self._zone, command.Volume.Param.UP)
        await self._manager.write(message)

    @override
    async def async_volume_down(self) -> None:
        """Decrease volume by 1 step."""
        message = command.Volume(self._zone, command.Volume.Param.DOWN)
        await self._manager.write(message)

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        message = command.Muting(
            self._zone, command.Muting.Param.ON if mute else command.Muting.Param.OFF
        )
        await self._manager.write(message)

    @override
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

    @override
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

    @override
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

    async def _net_operation(self, param: command.NetOperation.Param) -> None:
        await self._manager.write(command.NetOperation(param))

    @override
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._net_operation(command.NetOperation.Param.PLAY)

    @override
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._net_operation(command.NetOperation.Param.PAUSE)

    @override
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._net_operation(command.NetOperation.Param.STOP)

    @override
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._net_operation(command.NetOperation.Param.NEXT)

    @override
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._net_operation(command.NetOperation.Param.PREVIOUS)

    def process_update(self, message: status.Known) -> None:
        """Process update."""
        match message:
            case status.Power(param=status.Power.Param.ON):
                if self._attr_state != MediaPlayerState.ON:
                    self._query_state_delayed()
                self._attr_state = MediaPlayerState.ON
            case status.Power(param=status.Power.Param.STANDBY):
                self._attr_state = MediaPlayerState.OFF
                self.clear_net_playback()

            case status.Volume(param=volume):
                if not self._supports_volume:
                    self._attr_supported_features |= SUPPORTED_FEATURES_VOLUME
                    self._supports_volume = True
                # AMP_VOL / (VOL_RESOLUTION * (MAX_VOL / 100))
                volume_level: float = volume / (
                    self._volume_resolution * self._max_volume / 100
                )
                self._attr_volume_level = min(1, volume_level)

            case status.Muting(param=muting):
                self._attr_is_volume_muted = bool(muting is status.Muting.Param.ON)

            case status.InputSource(param=source):
                if source in self._source_mapping:
                    self._attr_source = self._source_mapping[source]
                else:
                    source_meaning = get_meaning(source)
                    _LOGGER.warning(
                        'Input source "%s" for entity: %s is not'
                        " in the list. Check integration options",
                        source_meaning,
                        self.entity_id,
                    )
                    self._attr_source = source_meaning

                if self._zone is Zone.MAIN:
                    self._update_net_input(source)

                self._query_av_info_delayed()

            case status.ListeningMode(param=sound_mode):
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
                        'Listening mode "%s" for entity: %s is'
                        " not in the list. Check integration"
                        " options",
                        sound_mode_meaning,
                        self.entity_id,
                    )
                    self._attr_sound_mode = sound_mode_meaning

                self._query_av_info_delayed()

            case status.HDMIOutput(param=hdmi_output):
                self._attr_extra_state_attributes[ATTR_VIDEO_OUT] = (
                    self._hdmi_output_mapping[hdmi_output]
                )
                self._query_av_info_delayed()

            case status.TunerPreset(param=preset):
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

            case (
                status.NetPlayStatus()
                | status.NetTitle()
                | status.NetArtist()
                | status.NetAlbum()
                | status.NetTrack()
                | status.NetTime()
                | status.NetJacketArt()
            ) if self._net_input is not None:
                self._process_net_update(message)

            case status.NotAvailable(kind=Kind.AUDIO_INFORMATION):
                # Not available right now, but still supported
                self._supports_audio_info = True

            case status.NotAvailable(kind=Kind.VIDEO_INFORMATION):
                # Not available right now, but still supported
                self._supports_video_info = True

        self.async_write_ha_state()

    def _query_state_delayed(self) -> None:
        if self._query_state_unsub is not None:
            self._query_state_unsub()
            self._query_state_unsub = None

        async def coro(_now: datetime) -> None:
            self._query_state_unsub = None
            await self.query_state()

        self._query_state_unsub = async_call_later(self.hass, QUERY_STATE_DELAY, coro)

    def _query_av_info_delayed(self) -> None:
        if self._zone is not Zone.MAIN or self._query_av_info_unsub is not None:
            return

        async def coro(_now: datetime) -> None:
            self._query_av_info_unsub = None
            if self._supports_audio_info:
                await self._manager.write(query.AudioInformation())
            if self._supports_video_info:
                await self._manager.write(query.VideoInformation())

        self._query_av_info_unsub = async_call_later(
            self.hass, QUERY_AV_INFO_DELAY, coro
        )

    def _update_net_input(self, source: InputSource) -> None:
        net_input = source if source in NET_SOURCES else None
        if net_input is self._net_input:
            # Repeated report of the same input
            return
        # Playback state belongs to the previous input
        self.clear_net_playback()
        if net_input is not None:
            self._net_input = net_input
            self._query_net_delayed()

    def _process_net_update(
        self,
        message: status.NetPlayStatus
        | status.NetTitle
        | status.NetArtist
        | status.NetAlbum
        | status.NetTrack
        | status.NetTime
        | status.NetJacketArt,
    ) -> None:
        match message:
            case status.NetJacketArt(image_type=image_type):
                # Other reports of this kind (such as "LINK" after the address) are ignored
                if (url := message.url) is not None:
                    self._net_art_url = url
                    self._net_art_serial += 1
                elif image_type is NetArtType.NONE:
                    self._net_art_url = None
            case status.NetPlayStatus(playback=playback) if playback is not None:
                self._set_net_state(NET_PLAYBACK_STATES[playback])
            case status.NetTitle(text=text):
                self._attr_media_title = text or None
                self._attr_media_content_type = MediaType.MUSIC
            case status.NetArtist(text=text):
                self._attr_media_artist = text or None
            case status.NetAlbum(text=text):
                self._attr_media_album_name = text or None
            case status.NetTrack(current=current):
                self._attr_media_track = current
            case status.NetTime(position=position, duration=duration):
                self._attr_media_duration = duration
                if self._net_position_jumped(position):
                    self._attr_media_position = position
                    self._attr_media_position_updated_at = (
                        dt_util.utcnow() if position is not None else None
                    )

    def _query_net_delayed(self) -> None:
        if self._query_net_unsub is not None:
            # Another input change restarts the delay
            self._query_net_unsub()
            self._query_net_unsub = None

        async def coro(_now: datetime) -> None:
            self._query_net_unsub = None
            if self._net_input is None:
                return
            await self._manager.write(query.NetPlayStatus())
            await self._manager.write(query.NetTitle())
            await self._manager.write(query.NetArtist())
            await self._manager.write(query.NetAlbum())
            await self._manager.write(query.NetTrack())
            await self._manager.write(query.NetTime())
            await self._manager.write(query.NetJacketArt())

        self._query_net_unsub = async_call_later(self.hass, QUERY_NET_DELAY, coro)

    def _expected_net_position(self) -> float | None:
        """Return the position HA extrapolates from the last one written."""
        position = self._attr_media_position
        updated_at = self._attr_media_position_updated_at
        if position is None or updated_at is None:
            return None
        if self.state is MediaPlayerState.PLAYING:
            return position + (dt_util.utcnow() - updated_at).total_seconds()
        return float(position)

    def _set_net_state(self, state: MediaPlayerState) -> None:
        if state is not self._net_state:
            # Anchor the position where the old state left it
            if (expected := self._expected_net_position()) is not None:
                self._attr_media_position = round(expected)
                self._attr_media_position_updated_at = dt_util.utcnow()
            self._net_state = state

    def _net_position_jumped(self, position: int | None) -> bool:
        """Return if a reported position differs from the extrapolated one."""
        expected = self._expected_net_position()
        if position is None or expected is None:
            return position != self._attr_media_position
        return abs(position - expected) > NET_POSITION_TOLERANCE
