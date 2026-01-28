# homeassistant/components/wiim/media_player.py
"""Support for WiiM Media Players."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from async_upnp_client.client import UpnpService, UpnpStateVariable
from wiim.consts import (
    PLAY_MEDIUMS_CTRL,
    SUPPORTED_INPUT_MODES_BY_MODEL,
    SUPPORTED_OUTPUT_MODES_BY_MODEL,
    TRACK_SOURCES_CTRL,
    VALID_PLAY_MEDIUMS,
    AudioOutputHwMode,
    InputMode,
    LoopMode as SDKLoopMode,
    PlayingStatus as SDKPlayingStatus,
    WiimHttpCommand,
    wiimDeviceType,
)
from wiim.exceptions import WiimException, WiimRequestException
from wiim.wiim_device import WiimDevice

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import DOMAIN, SDK_LOGGER, WiimData
from .entity import WiimBaseEntity, exception_wrap

MEDIA_TYPE_WIIM_LIBRARY = "wiim_library"
MEDIA_CONTENT_ID_ROOT = "library_root"
MEDIA_CONTENT_ID_FAVORITES = (
    f"{MEDIA_TYPE_WIIM_LIBRARY}/{MEDIA_CONTENT_ID_ROOT}/favorites"
)
MEDIA_CONTENT_ID_PLAYLISTS = (
    f"{MEDIA_TYPE_WIIM_LIBRARY}/{MEDIA_CONTENT_ID_ROOT}/playlists"
)

SDK_TO_HA_STATE: dict[SDKPlayingStatus, MediaPlayerState] = {
    SDKPlayingStatus.PLAYING: MediaPlayerState.PLAYING,
    SDKPlayingStatus.PAUSED: MediaPlayerState.PAUSED,
    SDKPlayingStatus.STOPPED: MediaPlayerState.IDLE,
    SDKPlayingStatus.LOADING: MediaPlayerState.BUFFERING,
}

# Define supported features
SUPPORT_WIIM_BASE = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.GROUPING
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SEEK
)

SUPPORT_WIIM_SEEKABLE = (
    MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SHUFFLE_SET
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WiiM media player from a config entry."""

    device: WiimDevice = entry.runtime_data

    # Store controller in hass.data if it's the first device, or update it
    wiim_data: WiimData = hass.data[DOMAIN]
    if not wiim_data.controller:
        pass

    # Create and add the media player entity
    entity = WiimMediaPlayerEntity(device, entry)
    async_add_entities([entity])


class WiimMediaPlayerEntity(WiimBaseEntity, MediaPlayerEntity):
    """Representation of a WiiM Media Player."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_name = None
    _attr_should_poll = False

    # Added to track if the current entity is a leader
    _is_group_leader: bool = False

    def __init__(self, device: WiimDevice, entry: ConfigEntry) -> None:
        """Initialize the WiiM entity."""
        super().__init__(device)
        self._entry = entry

        self._attr_unique_id = device.udn
        prefix_8 = self._extract_prefix(self._attr_unique_id)
        self.model_name = wiimDeviceType.get(prefix_8)

        # Initialize state attributes
        self._attr_state = MediaPlayerState.IDLE
        self._attr_volume_level: float | None = None
        self._attr_is_volume_muted: bool | None = None
        self._attr_media_content_id: str | None = None
        self._attr_media_content_type: MediaType | str | None = None
        self._attr_media_duration: int | None = None
        self._attr_media_position: int | None = None
        self._attr_media_position_updated_at: datetime | None = None
        self._attr_media_title: str | None = None
        self._attr_media_artist: str | None = None
        self._attr_media_album_name: str | None = None
        self._attr_media_album_artist: str | None = None
        self._attr_media_image_url: str | None = None
        self._attr_media_image_remotely_accessible = True
        self._attr_source: str | None = None
        self._attr_source_list: list[str] | None = self._generate_source_list()
        self._attr_shuffle: bool = False
        self._attr_repeat: RepeatMode | str = RepeatMode.OFF
        self._attr_sound_mode: str | None = None
        self._attr_sound_mode_list: list[str] | None = self._generate_output_list()
        self._attr_supported_features = SUPPORT_WIIM_BASE
        self._attr_group_members: list[str] | None = [self._attr_unique_id]

    def _extract_prefix(self, uuid_str: str) -> str:
        if not uuid_str.startswith("uuid:") or len(uuid_str) < 13:
            return ""
        return uuid_str[5:13]

    def _generate_source_list(self) -> list[str] | None:
        """Generate the list of available input sources based on model."""
        if self.model_name is None:
            return None

        modes_flag = SUPPORTED_INPUT_MODES_BY_MODEL.get(self.model_name)
        if modes_flag is None:
            return None

        return [mode.display_name for mode in InputMode if modes_flag & mode.value]  # type: ignore[attr-defined]

    def _generate_output_list(self) -> list[str] | None:
        """Generate the list of available audio output modes based on model."""
        if self.model_name is None:
            return None

        modes_flag = SUPPORTED_OUTPUT_MODES_BY_MODEL.get(self.model_name)
        if modes_flag is None:
            return None

        return [
            mode.display_name  # type: ignore[attr-defined]
            for mode in AudioOutputHwMode
            if modes_flag & mode.value
        ]

    @callback
    def _get_entity_id_for_udn(self, udn: str) -> str | None:
        """Helper to get a WiimMediaPlayerEntity ID by UDN from shared data."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if not wiim_data:
            SDK_LOGGER.warning("WiimData not found in hass.data.")
            return None

        for entity_id, stored_udn in wiim_data.entity_id_to_udn_map.items():
            if stored_udn == udn:
                return entity_id

        SDK_LOGGER.debug("No entity ID found for UDN: %s", udn)
        return None

    @callback
    def _update_ha_state_from_sdk_cache(self) -> None:
        """Update HA state from SDK's cache/HTTP poll attributes.

        This is the main method for updating this entity's HA attributes.
        Crucially, it also handles propagating metadata to followers if this is a leader.
        """
        SDK_LOGGER.debug(
            "Device %s: Updating HA state from SDK cache/HTTP poll",
            self.name or self.unique_id,
        )
        self._attr_available = self._device.available

        # Update DeviceInfo if name changes
        current_device_info_name = (
            self._attr_device_info.get("name") if self._attr_device_info else None
        )
        if self._device.name != current_device_info_name:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._device.udn)},
                name=self._device.name,
                manufacturer=self._device.manufacturer,
                model=self._device.model_name,
                sw_version=self._device.firmware_version,
            )
            if self._device.presentation_url:
                self._attr_device_info["configuration_url"] = (
                    self._device.presentation_url
                )
            elif self._device.http_api_url:
                self._attr_device_info["configuration_url"] = self._device.http_api_url

        if not self._attr_available:
            # If device is unavailable, clear media-related attributes
            self._attr_state = None
            self._attr_media_title = None
            self._attr_media_artist = None
            self._attr_media_album_name = None
            self._attr_media_image_url = None
            self._attr_media_duration = None
            self._attr_media_position = None
            self._attr_media_position_updated_at = None
            self._attr_source = None
            self._attr_sound_mode = None
            self._attr_supported_features = SUPPORT_WIIM_BASE
            # Update its own HA state
            if self.hass and self.entity_id:
                self.async_write_ha_state()
            return

        # Update common attributes first
        self._attr_volume_level = (
            float(self._device.volume) / 100.0
            if self._device.volume is not None
            else None
        )
        self._attr_is_volume_muted = self._device.is_muted

        # Determine current group role (leader/follower/standalone)
        group_info = None
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        is_current_device_leader = False
        if wiim_data and wiim_data.controller:
            group_info = wiim_data.controller.get_device_group_info(self._device.udn)
            if group_info and group_info.get("role") == "leader":
                is_current_device_leader = True
            elif group_info and group_info.get("role") == "follower":
                pass

        self._is_group_leader = is_current_device_leader

        if self._is_group_leader or (
            group_info and group_info.get("role") == "standalone"
        ):
            # This device is a leader or standalone, update its media metadata from its own SDK device state.
            if self._device.playing_status is not None:
                self._attr_state = SDK_TO_HA_STATE.get(
                    self._device.playing_status, MediaPlayerState.IDLE
                )

            if self._device.play_mode is not None:
                # Find the InputMode enum member by its value and then get its display_name
                try:
                    self._attr_source = self._device.play_mode
                except ValueError:
                    SDK_LOGGER.warning(
                        "Device %s: Unknown play_mode value from SDK: %s",
                        self.unique_id,
                        self._device.play_mode,
                    )
                    self._attr_source = InputMode.WIFI.display_name  # type: ignore[attr-defined]

            # Repeat and Shuffle modes
            current_loop_mode = self._device.loop_mode
            if current_loop_mode is not None:
                self.fromIntToRepeatShuffle(current_loop_mode)

            # Output Mode
            self._attr_sound_mode = self._device.output_mode

            # Current Track Info / Media Metadata
            if self._device.current_track_info:
                self._attr_media_title = self._device.current_track_info.get("title")
                self._attr_media_artist = self._device.current_track_info.get("artist")
                self._attr_media_album_name = self._device.current_track_info.get(
                    "album"
                )
                self._attr_media_image_url = self._device.current_track_info.get(
                    "albumArtURI"
                )
                self._attr_media_content_id = self._device.current_track_info.get("uri")
                self._attr_media_content_type = MediaType.MUSIC
                self._attr_media_duration = self._device.current_track_duration
                self._attr_media_position = self._device.current_position
                if self._attr_state == MediaPlayerState.PLAYING:
                    self._attr_media_position_updated_at = utcnow()
            else:
                # Clear media info if not playing or no track info
                self._attr_media_title = None
                self._attr_media_artist = None
                self._attr_media_album_name = None
                self._attr_media_image_url = None
                self._attr_media_content_id = None
                self._attr_media_content_type = None
                self._attr_media_duration = None
                self._attr_media_position = None
                self._attr_media_position_updated_at = None

        elif group_info and group_info.get("role") == "follower":
            # This device is a follower. It should actively pull metadata from its leader.
            leader_udn = group_info.get("leader_udn")
            if leader_udn:
                leader_entity_id = self._get_entity_id_for_udn(leader_udn)
                leader_state = (
                    self.hass.states.get(leader_entity_id) if leader_entity_id else None
                )

                if leader_state and leader_entity_id != self.entity_id:
                    SDK_LOGGER.debug(
                        f"Follower {self.entity_id}: Actively pulling metadata from leader {leader_entity_id}"
                    )
                    # Pull metadata from leader's state machine state
                    self._attr_media_title = leader_state.attributes.get("media_title")
                    self._attr_media_artist = leader_state.attributes.get(
                        "media_artist"
                    )
                    self._attr_media_album_name = leader_state.attributes.get(
                        "media_album_name"
                    )
                    # For image, use entity_picture from attributes, which might be a local proxy path
                    self._attr_media_image_url = leader_state.attributes.get(
                        "entity_picture"
                    )
                    self._attr_media_content_id = leader_state.attributes.get(
                        "media_content_id"
                    )
                    self._attr_media_content_type = leader_state.attributes.get(
                        "media_content_type"
                    )
                    self._attr_media_duration = leader_state.attributes.get(
                        "media_duration"
                    )
                    self._attr_media_position = leader_state.attributes.get(
                        "media_position"
                    )
                    self._attr_media_position_updated_at = leader_state.attributes.get(
                        "media_position_updated_at"
                    )
                    self._attr_source = leader_state.attributes.get("source")
                    self._attr_shuffle = leader_state.attributes.get("shuffle", False)
                    self._attr_repeat = leader_state.attributes.get(
                        "repeat", RepeatMode.OFF
                    )
                    self._attr_supported_features = leader_state.attributes.get(
                        "supported_features", SUPPORT_WIIM_BASE
                    )
                else:
                    SDK_LOGGER.debug(
                        f"Follower {self.entity_id}: Leader entity {leader_udn} not found or is self. Clearing own media metadata."
                    )
                    # If leader not found or is self (which means an inconsistent state), clear media info
                    self._attr_media_title = None
                    self._attr_media_artist = None
                    self._attr_media_album_name = None
                    self._attr_media_image_url = None
                    self._attr_media_content_id = None
                    self._attr_media_content_type = None
                    self._attr_media_duration = None
                    self._attr_media_position = None
                    self._attr_media_position_updated_at = None
                    self._attr_state = MediaPlayerState.IDLE
            else:
                SDK_LOGGER.debug(
                    f"Follower {self.entity_id}: No leader UDN found in group info. Clearing own media metadata."
                )
                # No leader_udn in group_info for a follower, clear media info
                self._attr_media_title = None
                self._attr_media_artist = None
                self._attr_media_album_name = None
                self._attr_media_image_url = None
                self._attr_media_content_id = None
                self._attr_media_content_type = None
                self._attr_media_duration = None
                self._attr_media_position = None
                self._attr_media_position_updated_at = None
                self._attr_state = MediaPlayerState.IDLE

        # Update the group_members attribute
        self._update_supported_features()

        # Always write HA state for this entity
        if self.hass and self.entity_id:
            self.async_write_ha_state()

    async def _update_output_mode(self) -> None:
        if self._device.supports_http_api:
            self._attr_sound_mode = await self._device.get_audio_output_hw_mode()
        else:
            SDK_LOGGER.error(
                f"Device {self.entity_id}: HTTP API not available for initial output mode fetch."
            )

    @callback
    def _handle_sdk_general_device_update(self, device: WiimDevice) -> None:
        """Handle general updates from the SDK (e.g., availability, polled data)."""
        SDK_LOGGER.debug(
            "Device %s: Received general SDK update from %s",
            self.entity_id,
            device.name,
        )
        if self._device.available:
            self.hass.async_create_task(
                self._async_handle_critical_error(WiimException("Device offline."))
            )
        else:
            self._device.set_available(True)

            async def _wrapped() -> None:
                await self._device.ensure_subscriptions()
                await self._update_output_mode()
                self._update_ha_state_from_sdk_cache()

            self.hass.async_create_task(_wrapped())

    @callback
    def _handle_sdk_av_transport_event(
        self, service: UpnpService, state_variables: list[UpnpStateVariable]
    ) -> None:
        """Handle AVTransport events from the SDK.

        This method updates the internal SDK device state based on events,
        then triggers a full HA state refresh from the device's cache.
        """

        SDK_LOGGER.debug(
            "Device %s: Received AVTransport event: %s",
            self.entity_id,
            self._device.event_data,
        )

        event_data = self._device.event_data

        if "TransportState" in event_data:
            sdk_status_str = event_data["TransportState"]
            try:
                sdk_status = SDKPlayingStatus(sdk_status_str)
                self._device.playing_status = sdk_status
                if sdk_status == SDKPlayingStatus.STOPPED:
                    SDK_LOGGER.debug(
                        f"Device {self.entity_id}: TransportState is STOPPED. Resetting media position and metadata."
                    )
                    self._device.current_position = 0
                    self._device.current_track_duration = 0
                    self._attr_media_position_updated_at = None
                    self._attr_media_duration = None
                    self._attr_media_position = None
                elif sdk_status in {SDKPlayingStatus.PAUSED, SDKPlayingStatus.PLAYING}:
                    self.hass.async_create_task(
                        self._device.sync_device_duration_and_position()
                    )
            except ValueError:
                SDK_LOGGER.warning(
                    "Device %s: Unknown TransportState from event: %s",
                    self.entity_id,
                    sdk_status_str,
                )

        self._update_ha_state_from_sdk_cache()

    @callback
    def _handle_sdk_rendering_control_event(
        self, service: UpnpService, state_variables: list[UpnpStateVariable]
    ) -> None:
        """Handle RenderingControl events from the SDK."""
        SDK_LOGGER.debug(
            "Device %s: Received RenderingControl event: %s",
            self.entity_id,
            state_variables,
        )

        self._update_ha_state_from_sdk_cache()

    @callback
    def _handle_sdk_play_queue_event(
        self, service: UpnpService, state_variables: list[UpnpStateVariable]
    ) -> None:
        """Handle PlayQueue events from the SDK (if implemented)."""
        SDK_LOGGER.debug(
            "Device %s: Received PlayQueue event: %s", self.entity_id, state_variables
        )
        self._update_ha_state_from_sdk_cache()

    def fromIntToRepeatShuffle(self, loopmode_val: Any) -> None:
        """Maps an integer loop mode value from SDK to Home Assistant RepeatMode and Shuffle state.

        Note: This mapping needs to be accurate for your SDKLoopMode enum.
        """
        try:
            loopmode_int = int(loopmode_val)
            loopmode_enum = SDKLoopMode(loopmode_int)

            if loopmode_enum == SDKLoopMode.SHUFFLE_DISABLE_REPEAT_ALL:
                self._attr_repeat = RepeatMode.ALL
                self._attr_shuffle = False
            elif loopmode_enum == SDKLoopMode.SHUFFLE_DISABLE_REPEAT_ONE:
                self._attr_repeat = RepeatMode.ONE
                self._attr_shuffle = False
            elif loopmode_enum == SDKLoopMode.SHUFFLE_ENABLE_REPEAT_ALL:
                self._attr_repeat = RepeatMode.ALL
                self._attr_shuffle = True
            elif loopmode_enum == SDKLoopMode.SHUFFLE_ENABLE_REPEAT_NONE:
                self._attr_repeat = RepeatMode.OFF
                self._attr_shuffle = True
            elif loopmode_enum == SDKLoopMode.SHUFFLE_DISABLE_REPEAT_NONE:
                self._attr_repeat = RepeatMode.OFF
                self._attr_shuffle = False
            elif loopmode_enum == SDKLoopMode.SHUFFLE_ENABLE_REPEAT_ONE:
                self._attr_repeat = RepeatMode.ONE
                self._attr_shuffle = True
            else:
                SDK_LOGGER.warning(
                    "Device %s: Unhandled SDKLoopMode value: %s",
                    self.entity_id,
                    loopmode_val,
                )
                self._attr_repeat = RepeatMode.OFF
                self._attr_shuffle = False

            SDK_LOGGER.debug(
                "Device %s: loopmode = %s (HA Repeat: %s, HA Shuffle: %s).",
                self.entity_id,
                loopmode_val,
                self._attr_repeat,
                self._attr_shuffle,
            )
        except ValueError:
            SDK_LOGGER.warning(
                "Device %s: Invalid loopmode value (not an integer): %s",
                self.entity_id,
                loopmode_val,
            )

    def fromRepeatToInt(self, repeat: RepeatMode) -> int:
        """Maps Home Assistant RepeatMode and current shuffle state to an SDK integer loop mode.

        This mapping needs to be consistent with your SDK's expectations.
        """
        if repeat == RepeatMode.ALL:
            return (
                SDKLoopMode.SHUFFLE_ENABLE_REPEAT_ALL.value
                if self._attr_shuffle
                else SDKLoopMode.SHUFFLE_DISABLE_REPEAT_ALL.value
            )
        if repeat == RepeatMode.ONE:
            return (
                SDKLoopMode.SHUFFLE_ENABLE_REPEAT_ONE.value
                if self._attr_shuffle
                else SDKLoopMode.SHUFFLE_DISABLE_REPEAT_ONE.value
            )
        if repeat == RepeatMode.OFF:
            return (
                SDKLoopMode.SHUFFLE_ENABLE_REPEAT_NONE.value
                if self._attr_shuffle
                else SDKLoopMode.SHUFFLE_DISABLE_REPEAT_NONE.value
            )
        return SDKLoopMode.SHUFFLE_DISABLE_REPEAT_NONE.value

    def fromShuffleToInt(self, shuffle: bool) -> int:
        """Maps Home Assistant shuffle state and current repeat mode to an SDK integer loop mode.

        This mapping needs to be consistent with your SDK's expectations.
        """
        if shuffle:
            if self._attr_repeat == RepeatMode.ALL:
                return SDKLoopMode.SHUFFLE_ENABLE_REPEAT_ALL.value
            if self._attr_repeat == RepeatMode.ONE:
                return SDKLoopMode.SHUFFLE_ENABLE_REPEAT_ONE.value
            if self._attr_repeat == RepeatMode.OFF:
                return SDKLoopMode.SHUFFLE_ENABLE_REPEAT_NONE.value
        elif self._attr_repeat == RepeatMode.ALL:
            return SDKLoopMode.SHUFFLE_DISABLE_REPEAT_ALL.value
        elif self._attr_repeat == RepeatMode.ONE:
            return SDKLoopMode.SHUFFLE_DISABLE_REPEAT_ONE.value
        elif self._attr_repeat == RepeatMode.OFF:
            return SDKLoopMode.SHUFFLE_DISABLE_REPEAT_NONE.value
        return SDKLoopMode.SHUFFLE_DISABLE_REPEAT_NONE.value

    def _update_support_features(self, features: MediaPlayerEntityFeature) -> None:
        """Update entity supported features and write state if changed."""
        if self._attr_supported_features != features:
            self._attr_supported_features = features
            if self.hass and self.entity_id:
                self.async_write_ha_state()

    async def _sync_follower_features(self, wiim_data: WiimData) -> bool:
        """Synchronize features if this device is a follower."""
        group_info = wiim_data.controller.get_device_group_info(self._device.udn)
        if not group_info or group_info.get("role") != "follower":
            return False

        leader_udn = group_info.get("leader_udn")
        if leader_udn:
            leader_entity_id = self._get_entity_id_for_udn(leader_udn)
            leader_state = (
                self.hass.states.get(leader_entity_id) if leader_entity_id else None
            )
            if leader_state and leader_entity_id != self.entity_id:
                leader_features = leader_state.attributes.get("supported_features")
                if leader_features is not None:
                    self._update_support_features(leader_features)
                    SDK_LOGGER.debug(
                        f"Device {self.entity_id}: Follower features synchronized from leader {leader_entity_id}."
                    )
                    return True

        # fallback to base features
        self._update_support_features(SUPPORT_WIIM_BASE)
        SDK_LOGGER.debug(f"Device {self.entity_id}: Follower set to base features.")
        return True

    async def _from_device_update_supported_features(self) -> None:
        """Fetches media info from the device to dynamically update supported features.

        This method is asynchronous and makes a network call.
        """
        # This will ensure _is_group_leader is set based on the latest group info from controller
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if not wiim_data or not wiim_data.controller:
            SDK_LOGGER.warning(
                "Device %s: Controller not available for _from_device_update_supported_features. Cannot determine group role.",
                self.entity_id,
            )
            return

        if await self._sync_follower_features(wiim_data):
            return

        try:
            if not self._device.supports_http_api:
                SDK_LOGGER.warning(
                    "Device %s: HTTP API not available to fetch MEDIA_INFO for supported features.",
                    self.entity_id,
                )

                self._attr_supported_features = SUPPORT_WIIM_BASE
                if self.hass and self.entity_id:
                    self.async_write_ha_state()
                return

            media_info = await self._device.async_set_AVT_cmd(
                WiimHttpCommand.MEDIA_INFO
            )

            if media_info is not None:
                playMedium = media_info.get("PlayMedium")
                if not isinstance(playMedium, str):
                    playMedium = ""

                trackSource = media_info.get("TrackSource")
                if not isinstance(trackSource, str):
                    trackSource = ""

            SDK_LOGGER.debug(
                "_from_device_update_supported_features PlayMedium = %s and trackSource = %s.",
                playMedium,
                trackSource,
            )

            current_features = SUPPORT_WIIM_BASE

            FLAGS = (
                MediaPlayerEntityFeature.NEXT_TRACK
                | MediaPlayerEntityFeature.PREVIOUS_TRACK
            )

            if isinstance(playMedium, str) and playMedium in PLAY_MEDIUMS_CTRL:
                current_features &= ~FLAGS  # Remove next/prev
            elif isinstance(trackSource, str) and trackSource in TRACK_SOURCES_CTRL:
                current_features |= MediaPlayerEntityFeature.NEXT_TRACK
                current_features &= ~MediaPlayerEntityFeature.PREVIOUS_TRACK
            else:
                current_features |= FLAGS  # Add next/prev back if not controlled

            FLAGS_LOOP_MODE = (
                MediaPlayerEntityFeature.REPEAT_SET
                | MediaPlayerEntityFeature.SHUFFLE_SET
            )

            # Check if PlayMedium is valid for loop mode (where repeat/shuffle ARE available)
            if (
                not (isinstance(playMedium, str) and playMedium in VALID_PLAY_MEDIUMS)
                or trackSource == ""
            ):
                current_features &= ~FLAGS_LOOP_MODE  # Remove repeat/shuffle
            else:
                current_features |= FLAGS_LOOP_MODE  # Add repeat/shuffle

            if self._attr_supported_features != current_features:
                self._attr_supported_features = current_features
                SDK_LOGGER.debug(
                    f"Device {self.entity_id}: Updated supported features to {current_features}"
                )
                if self.hass and self.entity_id:
                    self.async_write_ha_state()

        except WiimRequestException as e:
            SDK_LOGGER.warning(
                "Device %s: Failed to fetch MEDIA_INFO for supported features: %s",
                self.entity_id,
                e,
            )
            if self.hass and self.entity_id:
                self.async_write_ha_state()
        except Exception as e:
            SDK_LOGGER.error(
                "Device %s: Unexpected error in _from_device_update_supported_features: %s",
                self.entity_id,
                e,
                exc_info=True,
            )
            if self.hass and self.entity_id:
                self.async_write_ha_state()
            raise

    def _update_supported_features(self) -> None:
        """Update supported features based on current state."""
        self.hass.async_create_task(self._from_device_update_supported_features())

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        if self._device:
            self._device.general_event_callback = self._handle_sdk_general_device_update
            self._device.av_transport_event_callback = (
                self._handle_sdk_av_transport_event
            )
            self._device.rendering_control_event_callback = (
                self._handle_sdk_rendering_control_event
            )
            self._device.play_queue_event_callback = self._handle_sdk_play_queue_event
            SDK_LOGGER.debug(
                "Entity %s registered callbacks with WiimDevice %s",
                self.entity_id,
                self._device.name,
            )

            # Initialize SDK services and subscriptions
            init_success = await self._device.async_init_services_and_subscribe()

            if not init_success:
                if not self._device.available:
                    await self._device.disconnect()
                    SDK_LOGGER.debug(
                        "WiiM device reported as unavailable after init attempt."
                    )
                SDK_LOGGER.warning(
                    "Device %s initialized with potentially limited UPnP functionality. HTTP API might be primary.",
                    self._device.name,
                )
            else:
                # Fetch initial HTTP-based hardware output mode
                await self._update_output_mode()

            wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
            if wiim_data and self.entity_id:
                wiim_data.entity_id_to_udn_map[self.entity_id] = self._device.udn
                SDK_LOGGER.debug(
                    "Added %s (UDN: %s) to entity maps in hass.data.",
                    self.entity_id,
                    self._device.udn,
                )

            self._update_supported_features()

        self._update_ha_state_from_sdk_cache()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from Home Assistant."""
        if self._device:
            # Unregister SDK callbacks
            self._device.general_event_callback = None
            self._device.av_transport_event_callback = None
            self._device.rendering_control_event_callback = None
            self._device.play_queue_event_callback = None
            SDK_LOGGER.debug(
                "Entity %s unregistered callbacks from WiimDevice %s",
                self.entity_id,
                self._device.name,
            )
            await self._device.disconnect()

        # Remove entity_id from the global map
        if self.hass and self.entity_id:
            wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
            if wiim_data:
                if self.entity_id in wiim_data.entity_id_to_udn_map:
                    try:
                        del wiim_data.entity_id_to_udn_map[self.entity_id]
                        SDK_LOGGER.debug(
                            "Removed %s from entity_id_to_udn_map", self.entity_id
                        )
                    except KeyError:
                        SDK_LOGGER.debug(
                            "Entity %s not found in entity_id_to_udn_map for removal.",
                            self.entity_id,
                        )

        await super().async_will_remove_from_hass()

    async def _async_handle_critical_error(self, e: WiimException) -> None:
        """Handle critical communication errors, marking device unavailable and cleaning up."""
        SDK_LOGGER.warning(
            "Device %s encountered a critical communication error: %s",
            self.entity_id,
            e,
        )

        if not self._device.available:
            return

        SDK_LOGGER.info(
            "Device %s is now considered offline. Disconnecting UPnP subscriptions.",
            self.entity_id,
        )
        self._device.set_available(False)
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if not wiim_data or not wiim_data.controller:
            return
        controller = wiim_data.controller
        group_info = controller.get_device_group_info(self._device.udn)

        if group_info:
            current_role = group_info.get("role")
            if current_role == "leader":
                SDK_LOGGER.info(
                    "Device %s was a leader. Attempting to ungroup all its followers.",
                    self.entity_id,
                )

                # Cannot clear followers metadata directly anymore as we don't have access to their entities.
                # Followers must handle leader unavailability themselves.
            elif current_role == "follower":
                SDK_LOGGER.info(
                    "Device %s was a follower. Attempting to unjoin from its group.",
                    self.entity_id,
                )
                # await controller.async_ungroup_device(self._device.udn)

        await controller.async_update_all_multiroom_status()

        self._update_ha_state_from_sdk_cache()
        if self.hass and self.entity_id:
            self.async_write_ha_state()

    @exception_wrap
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0-1."""
        try:
            await self._device.async_set_volume(int(volume * 100))
            self._update_ha_state_from_sdk_cache()
        except WiimException as e:
            SDK_LOGGER.warning(f"Failed to set volume on {self.entity_id}: {e}")
            await self._async_handle_critical_error(e)
            raise HomeAssistantError(
                f"Failed to set volume on {self.entity_id}: {e}"
            ) from e

    @exception_wrap
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        try:
            await self._device.async_set_mute(mute)
            self._update_ha_state_from_sdk_cache()
        except WiimException as e:
            SDK_LOGGER.warning(f"Failed to mute volume on {self.entity_id}: {e}")
            await self._async_handle_critical_error(e)
            raise HomeAssistantError(
                f"Failed to mute volume on {self.entity_id}: {e}"
            ) from e

    async def _call_leader_service(self, service_name: str, **kwargs: Any) -> None:
        """Helper to call a media_player service on the group leader."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if not wiim_data or not wiim_data.controller:
            SDK_LOGGER.warning(
                "WiiM controller not available for redirection on %s.", self.entity_id
            )
            raise HomeAssistantError(
                f"WiiM controller not available. Cannot redirect {service_name} command."
            )

        controller = wiim_data.controller
        group_info = controller.get_device_group_info(self._device.udn)

        if group_info and group_info.get("role") == "follower":
            leader_udn = group_info.get("leader_udn")
            if leader_udn:
                leader_entity_id = self._get_entity_id_for_udn(leader_udn)
                if leader_entity_id and leader_entity_id != self.entity_id:
                    SDK_LOGGER.info(
                        "Redirecting %s command from follower %s to leader %s.",
                        service_name,
                        self.entity_id,
                        leader_entity_id,
                    )

                    service_data = {"entity_id": leader_entity_id}
                    service_data.update(kwargs)

                    await self.hass.services.async_call(
                        "media_player", service_name, service_data, blocking=True
                    )
                    return

                SDK_LOGGER.warning(
                    "Follower %s could not find a valid leader entity ID (%s) for redirection. Command %s will not be executed.",
                    self.entity_id,
                    leader_udn,
                    service_name,
                )
                raise HomeAssistantError(
                    f"Cannot redirect {service_name} command: Leader not found or invalid."
                )
            SDK_LOGGER.warning(
                "Follower %s has no leader UDN in group info. Command %s will not be executed.",
                self.entity_id,
                service_name,
            )
            raise HomeAssistantError(
                f"Cannot redirect {service_name} command: No leader UDN for follower."
            )

        SDK_LOGGER.warning(
            "Attempted to redirect command %s for a non-follower device %s. This is an internal logic error.",
            service_name,
            self.entity_id,
        )
        raise HomeAssistantError(
            f"Internal error: Command {service_name} redirection called on a non-follower."
        )

    @exception_wrap
    async def async_media_play(self) -> None:
        """Send play command."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if wiim_data and wiim_data.controller:
            group_info = wiim_data.controller.get_device_group_info(self._device.udn)
            if group_info and group_info.get("role") == "follower":
                try:
                    await self._call_leader_service("media_play")
                except HomeAssistantError:
                    if self._attr_available:
                        SDK_LOGGER.warning(
                            "Redirected play command failed for follower %s. Marking self unavailable.",
                            self.entity_id,
                        )
                        await self._async_handle_critical_error(
                            WiimException("Leader unavailable for play command")
                        )
                    raise
                else:
                    return

        try:
            SDK_LOGGER.debug(
                "Executing play command directly on %s (leader/standalone).",
                self.entity_id,
            )
            await self._device.async_play()
            self._update_ha_state_from_sdk_cache()
        except WiimException as e:
            SDK_LOGGER.warning(
                f"Failed to execute play command on {self.entity_id}: {e}"
            )
            await self._async_handle_critical_error(e)
            raise HomeAssistantError(f"Failed to play on {self.entity_id}: {e}") from e

    @exception_wrap
    async def async_media_pause(self) -> None:
        """Send pause command."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if wiim_data and wiim_data.controller:
            group_info = wiim_data.controller.get_device_group_info(self._device.udn)
            if group_info and group_info.get("role") == "follower":
                try:
                    await self._call_leader_service("media_pause")
                except HomeAssistantError:
                    if self._attr_available:
                        SDK_LOGGER.warning(
                            "Redirected pause command failed for follower %s. Marking self unavailable.",
                            self.entity_id,
                        )
                        await self._async_handle_critical_error(
                            WiimException("Leader unavailable for pause command")
                        )
                    raise
                else:
                    return

        try:
            SDK_LOGGER.debug(
                "Executing pause command directly on %s (leader/standalone).",
                self.entity_id,
            )
            await self._device.async_pause()
            await self._device.sync_device_duration_and_position()
            self._update_ha_state_from_sdk_cache()
        except WiimException as e:
            SDK_LOGGER.warning(
                f"Failed to execute pause command on {self.entity_id}: {e}"
            )
            await self._async_handle_critical_error(e)
            raise HomeAssistantError(f"Failed to pause on {self.entity_id}: {e}") from e

    @exception_wrap
    async def async_media_stop(self) -> None:
        """Send stop command."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if wiim_data and wiim_data.controller:
            group_info = wiim_data.controller.get_device_group_info(self._device.udn)
            if group_info and group_info.get("role") == "follower":
                try:
                    await self._call_leader_service("media_stop")
                except HomeAssistantError:
                    if self._attr_available:
                        SDK_LOGGER.warning(
                            "Redirected stop command failed for follower %s. Marking self unavailable.",
                            self.entity_id,
                        )
                        await self._async_handle_critical_error(
                            WiimException("Leader unavailable for stop command")
                        )
                    raise
                else:
                    return

        try:
            SDK_LOGGER.debug(
                "Executing stop command directly on %s (leader/standalone).",
                self.entity_id,
            )
            await self._device.async_stop()
            self._update_ha_state_from_sdk_cache()
        except WiimException as e:
            SDK_LOGGER.warning(
                f"Failed to execute stop command on {self.entity_id}: {e}"
            )
            await self._async_handle_critical_error(e)
            raise HomeAssistantError(f"Failed to stop on {self.entity_id}: {e}") from e

    @exception_wrap
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if wiim_data and wiim_data.controller:
            group_info = wiim_data.controller.get_device_group_info(self._device.udn)
            if group_info and group_info.get("role") == "follower":
                try:
                    await self._call_leader_service("media_next_track")
                except HomeAssistantError:
                    if self._attr_available:
                        SDK_LOGGER.warning(
                            "Redirected next_track command failed for follower %s. Marking self unavailable.",
                            self.entity_id,
                        )
                        await self._async_handle_critical_error(
                            WiimException("Leader unavailable for next track command")
                        )
                    raise
                else:
                    return

        try:
            SDK_LOGGER.debug(
                "Executing next_track command directly on %s (leader/standalone).",
                self.entity_id,
            )
            await self._device.async_next()
        except WiimException as e:
            SDK_LOGGER.warning(
                f"Failed to execute next_track command on {self.entity_id}: {e}"
            )
            await self._async_handle_critical_error(e)
            raise HomeAssistantError(
                f"Failed to move to next track on {self.entity_id}: {e}"
            ) from e

    @exception_wrap
    async def async_media_previous_track(self) -> None:
        """Send previous track track command."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if wiim_data and wiim_data.controller:
            group_info = wiim_data.controller.get_device_group_info(self._device.udn)
            if group_info and group_info.get("role") == "follower":
                try:
                    await self._call_leader_service("media_previous_track")
                except HomeAssistantError:
                    if self._attr_available:
                        SDK_LOGGER.warning(
                            "Redirected previous_track command failed for follower %s. Marking self unavailable.",
                            self.entity_id,
                        )
                        await self._async_handle_critical_error(
                            WiimException(
                                "Leader unavailable for previous track command"
                            )
                        )
                    raise
                else:
                    return

        try:
            SDK_LOGGER.debug(
                "Executing previous_track command directly on %s (leader/standalone).",
                self.entity_id,
            )
            await self._device.async_previous()
        except WiimException as e:
            SDK_LOGGER.warning(
                f"Failed to execute previous_track command on {self.entity_id}: {e}"
            )
            await self._async_handle_critical_error(e)
            raise HomeAssistantError(
                f"Failed to move to previous track on {self.entity_id}: {e}"
            ) from e

    @exception_wrap
    async def async_media_seek(self, position: float) -> None:
        """Seek to a specific position in the track."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if wiim_data and wiim_data.controller:
            group_info = wiim_data.controller.get_device_group_info(self._device.udn)
            if group_info and group_info.get("role") == "follower":
                try:
                    await self._call_leader_service(
                        "media_seek", seek_position=position
                    )
                except HomeAssistantError:
                    if self._attr_available:
                        SDK_LOGGER.warning(
                            "Redirected seek command failed for follower %s. Marking self unavailable.",
                            self.entity_id,
                        )
                        await self._async_handle_critical_error(
                            WiimException("Leader unavailable for seek command")
                        )
                    raise
                else:
                    return

        try:
            SDK_LOGGER.debug(
                "Executing seek command directly on %s (leader/standalone).",
                self.entity_id,
            )
            await self._device.async_seek(int(position))
        except WiimException as e:
            SDK_LOGGER.warning(
                f"Failed to execute seek command on {self.entity_id}: {e}"
            )
            await self._async_handle_critical_error(e)
            raise HomeAssistantError(f"Failed to seek on {self.entity_id}: {e}") from e

    @exception_wrap
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        SDK_LOGGER.debug(
            "async_play_media: type=%s, id=%s, kwargs=%s", media_type, media_id, kwargs
        )

        if media_type in {MediaType.MUSIC, MEDIA_TYPE_WIIM_LIBRARY}:
            try:
                preset_number = int(media_id)
                if not self._device.supports_http_api:
                    raise HomeAssistantError(
                        f"HTTP API not available for {self._device.name} to play preset."
                    )
                await self._device.play_preset(preset_number)
                self._attr_media_content_id = f"wiim_preset_{preset_number}"
                self._attr_media_content_type = MediaType.PLAYLIST
                self._attr_state = MediaPlayerState.PLAYING
            except ValueError:
                SDK_LOGGER.error(
                    "Invalid media_id for playlist/library: %s. Expected integer preset number.",
                    media_id,
                )
                raise HomeAssistantError(
                    f"Invalid media_id: {media_id}. Expected a valid preset number."
                ) from None
        elif media_type == MediaType.TRACK:
            try:
                track_index = int(media_id)
                await self._device.async_play_queue_with_index(track_index)
                self._attr_media_content_id = f"wiim_track_{track_index}"
                self._attr_media_content_type = MediaType.TRACK
                self._attr_state = MediaPlayerState.PLAYING
            except ValueError:
                SDK_LOGGER.error(
                    "Invalid media_id for track: %s. Expected integer track index.",
                    media_id,
                )
                raise HomeAssistantError(
                    f"Invalid media_id: {media_id}. Expected a valid track index."
                ) from None
        elif media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url

            url = async_process_play_media_url(self.hass, media_id)
            SDK_LOGGER.warning("media_type for play_media: %s", url)

            try:
                if not self._device.supports_http_api:
                    raise HomeAssistantError(
                        f"HTTP API not available for {self._device.name} to play preset."
                    )
                await self._device.play_url(url)
                self._attr_state = MediaPlayerState.PLAYING
            except ValueError:
                SDK_LOGGER.error(
                    "Invalid media_id for playlist/library: %s. Expected integer preset number.",
                    media_id,
                )
                raise HomeAssistantError(
                    f"Invalid media_id: {media_id}. Expected a valid preset number."
                ) from None
        else:
            SDK_LOGGER.warning("Unsupported media_type for play_media: %s", media_type)
            raise ServiceValidationError(f"Unsupported media type: {media_type}")

        if self.hass and self.entity_id:
            self.async_write_ha_state()

    @exception_wrap
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        sdk_loop_mode_int = self.fromRepeatToInt(repeat)
        await self._device.async_set_loop_mode(SDKLoopMode(sdk_loop_mode_int))
        self._update_ha_state_from_sdk_cache()

    @exception_wrap
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        sdk_loop_mode_int = self.fromShuffleToInt(shuffle)
        await self._device.async_set_loop_mode(SDKLoopMode(sdk_loop_mode_int))
        self._update_ha_state_from_sdk_cache()

    @exception_wrap
    async def async_select_source(self, source: str) -> None:
        """Select input mode."""
        try:
            await self._device.async_set_play_mode(source)
            self._update_ha_state_from_sdk_cache()
        except WiimException as e:
            SDK_LOGGER.error(f"Failed to select source on {self.entity_id}: {e}")
            await self._async_handle_critical_error(e)
            raise HomeAssistantError(
                f"Failed to select source on {self.entity_id}: {e}"
            ) from e

    @exception_wrap
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select output mode (e.g., optical, coaxial)."""

        try:
            if sound_mode == AudioOutputHwMode.OTHER_OUT.display_name:  # type: ignore[attr-defined]
                if self.hass and self.entity_id:
                    self.async_write_ha_state()
                return
            await self._device.async_set_output_mode(sound_mode)
            self._update_ha_state_from_sdk_cache()
        except WiimException as e:
            SDK_LOGGER.error(f"Failed to select output mode on {self.entity_id}: {e}")
            await self._async_handle_critical_error(e)
            raise HomeAssistantError(
                f"Failed to select output mode on {self.entity_id}: {e}"
            ) from e

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement media Browse helper."""
        SDK_LOGGER.debug(
            "Browsing media: content_type=%s, content_id=%s",
            media_content_type,
            media_content_id,
        )

        if media_content_id is not None and "media-source" in media_content_id:
            return await media_source.async_browse_media(
                self.hass,
                media_content_id,
                # This allows filtering content. In this case it will only show audio sources.
                content_filter=lambda item: item.media_content_type.startswith(
                    "audio/"
                ),
            )

        # Root browse
        if media_content_id is None or media_content_id == MEDIA_CONTENT_ID_ROOT:
            children: list[BrowseMedia] = []
            children.append(
                BrowseMedia(
                    media_class=MediaClass.DIRECTORY,
                    media_content_id=MEDIA_CONTENT_ID_FAVORITES,
                    media_content_type=MediaType.PLAYLIST,
                    title="Presets",
                    can_play=False,
                    can_expand=True,
                    thumbnail=None,
                ),
            )
            children.append(
                BrowseMedia(
                    media_class=MediaClass.DIRECTORY,
                    media_content_id=MEDIA_CONTENT_ID_PLAYLISTS,
                    media_content_type=MediaType.PLAYLIST,
                    title="Queue",
                    can_play=False,
                    can_expand=True,
                    thumbnail=None,
                ),
            )
            media_sources_item = await media_source.async_browse_media(
                self.hass,
                media_content_id,
                # This allows filtering content. In this case it will only show audio sources.
                content_filter=lambda item: item.media_content_type.startswith(
                    "audio/"
                ),
            )

            if media_sources_item.children:
                children.extend(media_sources_item.children)

            return BrowseMedia(
                media_class=MediaClass.DIRECTORY,
                media_content_id=MEDIA_CONTENT_ID_ROOT,
                media_content_type=MEDIA_TYPE_WIIM_LIBRARY,
                title=self._device.name,
                can_play=False,
                can_expand=True,
                children=children,
            )

        # Browsing Favorites
        if media_content_id == MEDIA_CONTENT_ID_FAVORITES:
            favorites_items = []
            try:
                sdk_favorites = await self._device.async_get_favorites()
                for item in sdk_favorites:
                    preset = item["name"]
                    if "_#~" in preset:
                        titles = preset.split("_#~")[0]
                    else:
                        titles = preset
                    favorites_items.append(
                        BrowseMedia(
                            media_class=MediaClass.PLAYLIST,
                            media_content_id=item["uri"],
                            media_content_type=MediaType.MUSIC,
                            title=titles,
                            can_play=True,
                            can_expand=False,
                            thumbnail=item.get("image_url"),
                        )
                    )
            except Exception as e:
                SDK_LOGGER.error("Error fetching favorites for browse_media: %s", e)
                raise

            return BrowseMedia(
                media_class=MediaClass.PLAYLIST,
                media_content_id=MEDIA_CONTENT_ID_FAVORITES,
                media_content_type=MediaType.PLAYLIST,
                title="Presets",
                can_play=False,
                can_expand=True,
                children=favorites_items,
            )

        # Browsing Playlists (flat list of tracks from current queue/playlist)
        if media_content_id == MEDIA_CONTENT_ID_PLAYLISTS:
            playlist_track_items: list = []
            try:
                sdk_playlist_tracks = await self._device.async_get_queue_items()
                trackSourceQueue = next(
                    (
                        item["SourceName"]
                        for item in sdk_playlist_tracks
                        if "SourceName" in item
                    ),
                    None,
                )

                media_info = await self._device.async_set_AVT_cmd(
                    WiimHttpCommand.MEDIA_INFO
                )
                playMedium = media_info.get("PlayMedium")
                trackSource = media_info.get("TrackSource")

                SDK_LOGGER.warning(
                    "MEDIA_CONTENT_ID_PLAYLISTS PlayMedium = %s and trackSource = %s and trackSourceQueue = %s.",
                    playMedium,
                    trackSource,
                    trackSourceQueue,
                )

                if playMedium not in VALID_PLAY_MEDIUMS:
                    return BrowseMedia(
                        media_class=MediaClass.PLAYLIST,
                        media_content_id=MEDIA_CONTENT_ID_PLAYLISTS,
                        media_content_type=MediaType.PLAYLIST,
                        title="Queue",
                        can_play=False,
                        can_expand=True,
                        children=playlist_track_items,
                    )

                if (
                    trackSourceQueue
                    and trackSource not in trackSourceQueue
                    and trackSourceQueue != "MyFavouriteQueue"
                ):
                    return BrowseMedia(
                        media_class=MediaClass.PLAYLIST,
                        media_content_id=MEDIA_CONTENT_ID_PLAYLISTS,
                        media_content_type=MediaType.PLAYLIST,
                        title="Queue",
                        can_play=False,
                        can_expand=True,
                        children=playlist_track_items,
                    )

                if trackSource == "":
                    return BrowseMedia(
                        media_class=MediaClass.PLAYLIST,
                        media_content_id=MEDIA_CONTENT_ID_PLAYLISTS,
                        media_content_type=MediaType.PLAYLIST,
                        title="Queue",
                        can_play=False,
                        can_expand=True,
                        children=playlist_track_items,
                    )

                for item in sdk_playlist_tracks:
                    uri = item.get("uri")
                    if not uri:
                        continue
                    playlist_track_items.append(
                        BrowseMedia(
                            media_class=MediaClass.TRACK,
                            media_content_id=str(item["uri"]),
                            media_content_type=MediaType.TRACK,
                            title=item["name"],
                            can_play=True,
                            can_expand=False,
                            thumbnail=item.get("image_url"),
                        )
                    )
            except Exception as e:
                SDK_LOGGER.error(
                    "Error fetching playlist tracks for browse_media: %s", e
                )
                raise

            return BrowseMedia(
                media_class=MediaClass.PLAYLIST,
                media_content_id=MEDIA_CONTENT_ID_PLAYLISTS,
                media_content_type=MediaType.PLAYLIST,
                title="Queue",
                can_play=False,
                can_expand=True,
                children=playlist_track_items,
            )

        if media_content_type and media_content_type.startswith("audio/"):
            return await media_source.async_browse_media(
                self.hass,
                media_content_id,
                content_filter=lambda item: item.media_content_type.startswith(
                    "audio/"
                ),
            )

        SDK_LOGGER.warning(
            "Unhandled browse_media request: content_type=%s, content_id=%s",
            media_content_type,
            media_content_id,
        )
        raise BrowseError(f"Invalid browse path: {media_content_id}")
