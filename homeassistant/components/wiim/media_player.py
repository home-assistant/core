# homeassistant/components/wiim/media_player.py
"""Support for WiiM Media Players."""

from __future__ import annotations

import asyncio
from datetime import datetime
from html import unescape
import json
from typing import Any

from async_upnp_client.client import UpnpService, UpnpStateVariable
from defusedxml import ElementTree as ET
import voluptuous as vol
from wiim.consts import (
    AUDIO_AUX_MODE_IDS,
    CMD_TO_MODE_MAP,
    PLAY_MEDIUMS_CTRL,
    SUPPORTED_INPUT_MODES_BY_MODEL,
    SUPPORTED_OUTPUT_MODES_BY_MODEL,
    TRACK_SOURCES_CTRL,
    VALID_PLAY_MEDIUMS,
    AudioOutputHwMode,
    InputMode,
    LoopMode as SDKLoopMode,
    PlayingStatus as SDKPlayingStatus,
    PlayMediumToInputMode,
    WiimHttpCommand,
    wiimDeviceType,
)
from wiim.exceptions import WiimException, WiimRequestException
from wiim.handler import parse_last_change_event
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
from homeassistant.helpers import config_validation as cv, entity_platform
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
    # SDKPlayingStatus.UNKNOWN: MediaPlayerState.IDLE,
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
    # | MediaPlayerEntityFeature.REPEAT_SET
    # | MediaPlayerEntityFeature.SHUFFLE_SET
)

SUPPORT_WIIM_SEEKABLE = (
    MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SHUFFLE_SET
)

# Service definitions
SERVICE_PLAY_PRESET = "play_preset"
ATTR_PRESET_NUMBER = "preset_number"
SERVICE_PLAY_PRESET_SCHEMA = cv.make_entity_service_schema(
    {vol.Required(ATTR_PRESET_NUMBER): cv.positive_int}
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WiiM media player from a config entry."""
    # Ensure WiimData is initialized in hass.data
    # Initialize entities_by_entity_id as an empty dictionary here
    # if DOMAIN not in hass.data:
    #     hass.data[DOMAIN] = WiimData(
    #         controller=None, entity_id_to_udn_map={}, entities_by_entity_id={}
    #     )

    device: WiimDevice = entry.runtime_data
    if not isinstance(device, WiimDevice):
        SDK_LOGGER.error(
            "Config entry runtime_data is not a WiimDevice instance. Found: %s",
            type(device).__name__,
        )
        return

    # Store controller in hass.data if it's the first device, or update it
    wiim_data: WiimData = hass.data[DOMAIN]
    if not wiim_data.controller:
        pass

    platform = entity_platform.async_get_current_platform()
    if platform:
        platform.async_register_entity_service(
            SERVICE_PLAY_PRESET, SERVICE_PLAY_PRESET_SCHEMA, "async_play_preset_service"
        )

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

        # source_list: list[str] = []
        # for mode in InputMode:
        #     if modes_flag & mode.value:
        #         source_list.append(mode.display_name)  # type: ignore[attr-defined]
        # return source_list
        return [mode.display_name for mode in InputMode if modes_flag & mode.value]  # type: ignore[attr-defined]

    def _generate_output_list(self) -> list[str] | None:
        """Generate the list of available audio output modes based on model."""
        if self.model_name is None:
            return None

        modes_flag = SUPPORTED_OUTPUT_MODES_BY_MODEL.get(self.model_name)
        if modes_flag is None:
            return None

        # output_list: list[str] = []
        # for mode in AudioOutputHwMode:
        #     if modes_flag & mode.value:
        #         output_list.append(mode.display_name)  # type: ignore[attr-defined]
        # return output_list
        return [
            mode.display_name  # type: ignore[attr-defined]
            for mode in AudioOutputHwMode
            if modes_flag & mode.value
        ]

    @callback
    def _get_entity_for_udn(self, udn: str) -> WiimMediaPlayerEntity | None:
        """Helper to get a WiimMediaPlayerEntity instance by UDN from shared data."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if not wiim_data:
            SDK_LOGGER.warning("WiimData not found in hass.data.")
            return None

        found_entity_id = None
        for entity_id, stored_udn in wiim_data.entity_id_to_udn_map.items():
            SDK_LOGGER.debug(
                "Checking entity_id: %s with stored UDN: %s", entity_id, stored_udn
            )
            if stored_udn == udn:
                found_entity_id = entity_id
                SDK_LOGGER.debug("Match found: entity_id = %s", found_entity_id)
                break

        if found_entity_id:
            entity = wiim_data.entities_by_entity_id.get(found_entity_id)
            SDK_LOGGER.debug(
                "Retrieved entity object for %s: %s", found_entity_id, entity
            )
            return entity

        SDK_LOGGER.debug("No entity found for UDN: %s", udn)
        return None

    @callback
    def _get_entity_for_entity_id(self, entity_id: str) -> WiimMediaPlayerEntity | None:
        """Helper to get a WiimMediaPlayerEntity instance by entity_id."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if not wiim_data:
            SDK_LOGGER.warning("WiimData not found in hass.data.")
            return None
        # Directly retrieve the entity object from the entities_by_entity_id map
        return wiim_data.entities_by_entity_id.get(entity_id)

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
                manufacturer=self._device._manufacturer,  # noqa: SLF001
                model=self._device.model_name,
                sw_version=self._device.firmware_version,
            )
            if self._device._presentation_url:  # noqa: SLF001
                self._attr_device_info["configuration_url"] = (
                    self._device._presentation_url  # noqa: SLF001
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
                # if self._attr_state in [MediaPlayerState.PLAYING, MediaPlayerState.PAUSED]:
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
                leader_entity = self._get_entity_for_udn(leader_udn)
                if leader_entity and leader_entity.entity_id != self.entity_id:
                    SDK_LOGGER.debug(
                        f"Follower {self.entity_id}: Actively pulling metadata from leader {leader_entity.entity_id}"
                    )
                    # Construct leader_media_attrs from leader_entity's current state attributes
                    leader_media_attrs = {
                        "state": leader_entity.state,
                        "media_title": leader_entity.media_title,
                        "media_artist": leader_entity.media_artist,
                        "media_album_name": leader_entity.media_album_name,
                        "media_image_url": leader_entity.media_image_url,
                        "media_content_id": leader_entity.media_content_id,
                        "media_content_type": leader_entity.media_content_type,
                        "media_duration": leader_entity.media_duration,
                        "media_position": leader_entity.media_position,
                        "media_position_updated_at": leader_entity.media_position_updated_at,
                        "source": leader_entity.source,
                        "shuffle": leader_entity.shuffle,
                        "repeat": leader_entity.repeat,
                        "supported_features": leader_entity.supported_features,
                    }
                    self.hass.async_create_task(
                        self._async_apply_leader_metadata(leader_media_attrs)
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
        self._update_group_members_attribute()
        self._update_supported_features()

        # Always write HA state for this entity
        if self.hass and self.entity_id:
            self.async_write_ha_state()

            # This is the PUSH mechanism from the leader.
            if self._is_group_leader and self._attr_group_members:
                SDK_LOGGER.debug(
                    "Leader %s is propagating metadata to followers: %s",
                    self.entity_id,
                    self._attr_group_members,
                )

                # Capture the leader's current media state attributes
                leader_media_attrs = {
                    "state": self._attr_state,
                    "media_title": self._attr_media_title,
                    "media_artist": self._attr_media_artist,
                    "media_album_name": self._attr_media_album_name,
                    "media_image_url": self._attr_media_image_url,
                    "media_content_id": self._attr_media_content_id,
                    "media_content_type": self._attr_media_content_type,
                    "media_duration": self._attr_media_duration,
                    "media_position": self._attr_media_position,
                    "media_position_updated_at": self._attr_media_position_updated_at,
                    "source": self._attr_source,
                    "shuffle": self._attr_shuffle,
                    "repeat": self._attr_repeat,
                    "supported_features": self._attr_supported_features,
                }

                for member_entity_id in self._attr_group_members:
                    if member_entity_id == self.entity_id:
                        continue

                    # Get the follower's actual entity object using its entity_id
                    follower_entity = self._get_entity_for_entity_id(member_entity_id)
                    if follower_entity and follower_entity != self:
                        SDK_LOGGER.debug(
                            "Propagating metadata to follower %s",
                            follower_entity.entity_id,
                        )
                        # Schedule an immediate update for the follower
                        self.hass.async_create_task(
                            follower_entity._async_apply_leader_metadata(  # noqa: SLF001
                                leader_media_attrs
                            )
                        )
                    else:
                        SDK_LOGGER.debug(
                            "Follower entity %s not found or is self (should have been skipped if self).",
                            member_entity_id,
                        )

    async def _async_apply_leader_metadata(self, leader_attrs: dict[str, Any]) -> None:
        """Callback method for followers to receive and apply metadata from the group leader.

        This method will be called directly by the leader's entity.
        """
        SDK_LOGGER.debug(
            "Follower %s: Applying metadata from leader: %s",
            self.entity_id,
            leader_attrs,
        )

        # Apply the leader's state and media attributes to this follower entity
        if self._attr_state != leader_attrs["state"]:
            self._attr_state = leader_attrs["state"]
        if self._attr_media_title != leader_attrs["media_title"]:
            self._attr_media_title = leader_attrs["media_title"]
        if self._attr_media_artist != leader_attrs["media_artist"]:
            self._attr_media_artist = leader_attrs["media_artist"]
        if self._attr_media_album_name != leader_attrs["media_album_name"]:
            self._attr_media_album_name = leader_attrs["media_album_name"]
        if self._attr_media_image_url != leader_attrs["media_image_url"]:
            self._attr_media_image_url = leader_attrs["media_image_url"]
        if self._attr_media_content_id != leader_attrs["media_content_id"]:
            self._attr_media_content_id = leader_attrs["media_content_id"]
        if self._attr_media_content_type != leader_attrs["media_content_type"]:
            self._attr_media_content_type = leader_attrs["media_content_type"]
        if self._attr_media_duration != leader_attrs["media_duration"]:
            self._attr_media_duration = leader_attrs["media_duration"]
        if self._attr_media_position != leader_attrs["media_position"]:
            self._attr_media_position = leader_attrs["media_position"]
            # Position update timestamp is crucial for accurate progress bar in HA
        # self._attr_media_position_updated_at = leader_attrs["media_position_updated_at"]
        # self._device.current_position = leader_attrs["media_position"]
        # self._device.current_track_duration = leader_attrs["media_duration"]
        self._attr_media_position_updated_at = utcnow()
        if self._attr_source != leader_attrs["source"]:
            self._attr_source = leader_attrs["source"]
        if self._attr_shuffle != leader_attrs["shuffle"]:
            self._attr_shuffle = leader_attrs["shuffle"]
        if self._attr_repeat != leader_attrs["repeat"]:
            self._attr_repeat = leader_attrs["repeat"]

        if self._attr_supported_features != leader_attrs["supported_features"]:
            self._attr_supported_features = leader_attrs["supported_features"]
            SDK_LOGGER.debug(
                f"Follower {self.entity_id}: Updated supported features from leader."
            )

        SDK_LOGGER.debug(
            "Follower %s: Applied leader metadata. State: %s, Title: '%s', Artist: '%s', Album: '%s', Image: '%s'",
            self.entity_id,
            self._attr_state,
            self._attr_media_title,
            self._attr_media_artist,
            self._attr_media_album_name,
            self._attr_media_image_url,
        )

        # Final HA state write for this follower
        self.async_write_ha_state()

    async def _aysnc_handle_group_status(self) -> None:
        """Handle general update group status."""
        SDK_LOGGER.debug(
            "Device %s: Handle general update group status.", self.entity_id
        )
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if wiim_data and wiim_data.controller:
            controller = wiim_data.controller
            await controller.async_update_all_multiroom_status()

    async def _update_output_mode(self) -> None:
        if self._device._http_api:  # noqa: SLF001
            try:
                hardware_output_mode = await self._device._http_request(  # noqa: SLF001
                    WiimHttpCommand.AUDIO_OUTPUT_HW_MODE
                )
                output_mode = int(hardware_output_mode["hardware"])
                source_mode = int(hardware_output_mode["source"])
                if source_mode == 1:
                    self._attr_sound_mode = AudioOutputHwMode.OTHER_OUT.display_name  # type: ignore[attr-defined]
                elif (
                    self._attr_unique_id
                    and any(key in self._attr_unique_id for key in AUDIO_AUX_MODE_IDS)
                    and output_mode == 2
                ):
                    self._attr_sound_mode = AudioOutputHwMode.SPEAKER_OUT.display_name  # type: ignore[attr-defined]
                else:

                    def get_output_mode_display_name_by_cmd(
                        cmd: int,
                    ) -> str:
                        mode = CMD_TO_MODE_MAP.get(cmd)
                        if mode:
                            return mode.display_name  # type: ignore[attr-defined]
                        return AudioOutputHwMode.OTHER_OUT.display_name  # type: ignore[attr-defined]

                    try:
                        self._attr_sound_mode = get_output_mode_display_name_by_cmd(
                            output_mode
                        )
                    except ValueError:
                        self._attr_sound_mode = AudioOutputHwMode.OTHER_OUT.display_name  # type: ignore[attr-defined]
                        SDK_LOGGER.debug("Output mode is out range.")
            except WiimRequestException as e:
                SDK_LOGGER.error(
                    f"Device {self.entity_id}: Failed to get initial HTTP output mode: {e}"
                )
            except Exception as e:
                SDK_LOGGER.error(
                    f"Device {self.entity_id}: Unexpected error fetching initial HTTP output mode: {e}",
                    exc_info=True,
                )
                raise
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
            self._device._available = True  # noqa: SLF001

            async def _wrapped() -> None:
                result = await self._device._renew_subscriptions()  # noqa: SLF001
                if not result:
                    self._device._available = True  # noqa: SLF001
                    await self._device.async_init_services_and_subscribe()
                    await self._device._renew_subscriptions()  # noqa: SLF001
                await self._update_output_mode()
                self._update_ha_state_from_sdk_cache()
                await self._aysnc_handle_group_status()

            self.hass.async_create_task(_wrapped())

    async def _sync_device_duration_and_position(self):
        try:
            # Call GetPositionInfo directly on the AVTransport service
            position_response = await self._device.async_set_AVT_cmd(
                WiimHttpCommand.POSITION_INFO
            )
            position_str = position_response.get("RelTime")
            duration_str = position_response.get("TrackDuration")
            if position_str:
                position = self._device._parse_duration(position_str)  # noqa: SLF001
                position = max(position, 0)
                duration = self._device._parse_duration(duration_str)  # noqa: SLF001
                self._device.current_position = position
                self._device.current_track_duration = duration
                self._attr_media_duration = duration
                self._attr_media_position = position
                # self._attr_media_position_updated_at = utcnow()
                SDK_LOGGER.debug(
                    f"Device {self.entity_id}: Fetched position {position} from GetPositionInfo after play command."
                )
            else:
                SDK_LOGGER.debug(
                    f"Device {self.entity_id}: No RelTime in GetPositionInfo response after play command."
                )
        except Exception as e:
            SDK_LOGGER.warning(
                f"Device {self.entity_id}: Failed to get position info from GetPositionInfo after play: {e}"
            )
            raise

        self._update_ha_state_from_sdk_cache()

    @callback
    def _handle_sdk_av_transport_event(
        self, service: UpnpService, state_variables: list[UpnpStateVariable]
    ) -> None:
        """Handle AVTransport events from the SDK.

        This method updates the internal SDK device state based on events,
        then triggers a full HA state refresh from the device's cache.
        """
        SDK_LOGGER.debug(
            "Device %s: Received AVTransport event: %s", self.entity_id, state_variables
        )
        last_change_sv = next(
            (sv for sv in state_variables if sv.name == "LastChange"), None
        )
        if not last_change_sv or last_change_sv.value is None:
            SDK_LOGGER.debug(
                "Device %s: No LastChange in AVTransport event or value is None.",
                self.entity_id,
            )
            return

        try:
            event_data = parse_last_change_event(str(last_change_sv.value), SDK_LOGGER)
        except Exception as e:
            SDK_LOGGER.error(
                "Device %s: Error parsing AVTransport LastChange event: %s. Data: %s",
                self.entity_id,
                e,
                last_change_sv.value,
                exc_info=True,
            )
            raise

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
                    # self._device.current_track_info = {}
                    self._attr_media_position_updated_at = None
                    # self._attr_media_title = None
                    # self._attr_media_artist = None
                    # self._attr_media_album_name = None
                    # self._attr_media_image_url = None
                    # self._attr_media_content_id = None
                    # self._attr_media_content_type = None
                    self._attr_media_duration = None
                    self._attr_media_position = None
                elif sdk_status in {SDKPlayingStatus.PAUSED, SDKPlayingStatus.PLAYING}:
                    self.hass.async_create_task(
                        self._sync_device_duration_and_position()
                    )
            except ValueError:
                SDK_LOGGER.warning(
                    "Device %s: Unknown TransportState from event: %s",
                    self.entity_id,
                    sdk_status_str,
                )

        if "CurrentTrackDuration" in event_data:
            duration = self._device._parse_duration(event_data["CurrentTrackDuration"])  # noqa: SLF001
            self._device.current_track_duration = duration

        if "RelativeTimePosition" in event_data:
            position = self._device._parse_duration(event_data["RelativeTimePosition"])  # noqa: SLF001
            position = max(position, 0)
            self._device.current_position = position
            self._attr_media_position_updated_at = utcnow()

        if "A_ARG_TYPE_SeekTarget" in event_data:
            position_str = event_data["A_ARG_TYPE_SeekTarget"]
            SDK_LOGGER.debug(
                f"Device {self.entity_id}: Using A_ARG_TYPE_SeekTarget: {position_str}"
            )

            if position_str:
                try:
                    position = self._device._parse_duration(position_str)  # noqa: SLF001
                    self._device.current_position = position
                    self._attr_media_position_updated_at = utcnow()
                    SDK_LOGGER.debug(
                        f"Device {self.entity_id}: Updated media position to {position} seconds."
                    )
                except ValueError:
                    SDK_LOGGER.warning(
                        f"Device {self.entity_id}: Could not parse position string '{position_str}'."
                    )

        if "PlaybackStorageMedium" in event_data:
            playMedium = PlayMediumToInputMode.get(
                event_data["PlaybackStorageMedium"], 1
            )
            new_mode = InputMode(playMedium)  # type: ignore[call-arg]
            self._device.play_mode = new_mode.display_name  # type: ignore[attr-defined]

        # Prioritize AVTransportURIMetaData for media metadata if available, otherwise fallback to CurrentTrackMetaData
        media_metadata_key = None
        if event_data.get("AVTransportURIMetaData"):
            media_metadata_key = "AVTransportURIMetaData"
        elif event_data.get("CurrentTrackMetaData"):
            media_metadata_key = "CurrentTrackMetaData"

        if media_metadata_key:
            try:
                meta = event_data[media_metadata_key]
                if isinstance(meta, str):
                    SDK_LOGGER.warning(
                        "Device %s: %s is raw XML in event, not parsed by SDK. Attempting to parse.",
                        self.entity_id,
                        media_metadata_key,
                    )
                    try:
                        root = ET.fromstring(unescape(meta))
                        didl_ns = {
                            "didl": "urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/",
                            "dc": "http://purl.org/dc/elements/1.1/",
                            "upnp": "urn:schemas-upnp-org:metadata-1-0/upnp/",
                        }
                        item_elem = root.find("didl:item", namespaces=didl_ns)
                        if item_elem is not None:
                            res_elem = item_elem.find("res", namespaces=didl_ns)
                        else:
                            res_elem = None

                        duration_str = (
                            res_elem.get("duration", "") if res_elem is not None else ""
                        )
                        try:
                            duration = int(duration_str) if duration_str else 0
                        except ValueError:
                            duration = 0

                        if item_elem:
                            meta = {
                                "title": item_elem.findtext(
                                    "dc:title", default="", namespaces=didl_ns
                                ),
                                "artist": item_elem.findtext(
                                    "upnp:artist", default="", namespaces=didl_ns
                                ),
                                "album": item_elem.findtext(
                                    "upnp:album", default="", namespaces=didl_ns
                                ),
                                "albumArtURI": item_elem.findtext(
                                    "upnp:albumArtURI", default="", namespaces=didl_ns
                                ),
                                "res": item_elem.findtext(
                                    "res", default="", namespaces=didl_ns
                                ),
                                "duration": duration,
                            }
                        else:
                            SDK_LOGGER.warning(
                                "Device %s: No 'item' element found in parsed %s XML.",
                                self.entity_id,
                                media_metadata_key,
                            )
                            meta = {}
                    except ET.ParseError as xml_e:
                        SDK_LOGGER.error(
                            "Device %s: Failed to parse XML from %s: %s",
                            self.entity_id,
                            media_metadata_key,
                            xml_e,
                        )
                        meta = {}

                # Update the device's internal current_track_info dictionary
                self._device.current_track_info = {
                    "title": meta.get("title"),
                    "artist": meta.get("artist"),
                    "album": meta.get("album"),
                    "uri": meta.get("res"),
                    "duration": (
                        self._device._parse_duration(meta.get("duration"))  # noqa: SLF001
                        if meta.get("duration")
                        else None
                    ),
                    "albumArtURI": self._device._make_absolute_url(  # noqa: SLF001
                        meta.get("albumArtURI")
                    ),
                }

            except Exception as e:
                SDK_LOGGER.error(
                    "Device %s: Error processing metadata from %s AVTransport event: %s",
                    self.entity_id,
                    media_metadata_key,
                    e,
                    exc_info=True,
                )
                raise

        self._update_ha_state_from_sdk_cache()

    async def _async_process_rendering_control_event(self, last_change_sv: str) -> None:
        # New: Handle Slave action="add" and Slave action="del" events
        raw_xml_value = last_change_sv
        try:
            root = ET.fromstring(raw_xml_value)
            rcs_ns = {"rcs": "urn:schemas-upnp-org:metadata-1-0/RCS/"}
            instance_id_elem = root.find(".//rcs:InstanceID", namespaces=rcs_ns)

            if instance_id_elem:
                slave_elements = instance_id_elem.findall(
                    ".//rcs:Slave", namespaces=rcs_ns
                )
                for slave_elem in slave_elements:
                    action = slave_elem.get("action")
                    slave_udn = slave_elem.get("val")

                    if action and slave_udn:
                        SDK_LOGGER.debug(
                            f"Device {self.entity_id}: Detected Slave action='{action}' for UDN='{slave_udn}'"
                        )

                        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
                        if not wiim_data or not wiim_data.controller:
                            SDK_LOGGER.warning(
                                "WiimData or controller not available to handle Slave action."
                            )
                            self._update_ha_state_from_sdk_cache()
                            return

                        controller = wiim_data.controller

                        SDK_LOGGER.debug(
                            f"Triggering controller multiroom status update for device {self._device.udn} and slave {slave_udn}"
                        )

                        await asyncio.sleep(1)
                        await controller.async_update_multiroom_status(self._device)

                        def restore_uuid(cleaned):
                            prefix = cleaned[:8]
                            part1 = cleaned[0:8]
                            part2 = cleaned[8:12]
                            part3 = cleaned[12:16]
                            part4 = cleaned[16:20]
                            part5 = cleaned[20:] + prefix
                            return f"uuid:{part1}-{part2}-{part3}-{part4}-{part5}"

                        slave_ha_entity = self._get_entity_for_udn(
                            restore_uuid(slave_udn)
                        )
                        if slave_ha_entity and slave_ha_entity != self:
                            if action == "rm":
                                SDK_LOGGER.debug(
                                    f"Slave {slave_ha_entity.entity_id} removed from group, clearing metadata."
                                )

                                slave_ha_entity._attr_state = MediaPlayerState.IDLE  # noqa: SLF001
                                slave_ha_entity._attr_media_title = None  # noqa: SLF001
                                slave_ha_entity._attr_media_artist = None  # noqa: SLF001
                                slave_ha_entity._attr_media_album_name = None  # noqa: SLF001
                                slave_ha_entity._attr_media_image_url = None  # noqa: SLF001
                                slave_ha_entity._attr_media_content_id = None  # noqa: SLF001
                                slave_ha_entity._attr_media_content_type = None  # noqa: SLF001
                                # slave_ha_entity._attr_media_duration = None
                                # slave_ha_entity._attr_media_position = None
                                # slave_ha_entity._attr_media_position_updated_at = None
                                slave_ha_entity.async_write_ha_state()  # Write state immediately
                            elif action == "add":
                                SDK_LOGGER.debug(
                                    f"Slave {slave_ha_entity.entity_id} added to group, triggering full state update for it."
                                )

                                async def _wrapped() -> None:
                                    await self._aysnc_handle_group_status()
                                    self._update_ha_state_from_sdk_cache()

                                self.hass.async_create_task(_wrapped())
                        elif slave_ha_entity == self:
                            SDK_LOGGER.debug(
                                f"Slave entity {slave_udn} is the current entity. State will be updated by current entity's _update_ha_state_from_sdk_cache call."
                            )

        except ET.ParseError as xml_e:
            SDK_LOGGER.warning(
                f"Device {self.entity_id}: Failed to parse XML for Slave action in RenderingControl event: {xml_e}"
            )
        except Exception as general_e:
            SDK_LOGGER.error(
                f"Device {self.entity_id}: Unexpected error processing Slave action in RenderingControl event: {general_e}",
                exc_info=True,
            )
            raise

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
        last_change_sv = next(
            (sv for sv in state_variables if sv.name == "LastChange"), None
        )
        if not last_change_sv or last_change_sv.value is None:
            SDK_LOGGER.debug(
                "Device %s: No LastChange in RenderingControl event or value is None.",
                self.entity_id,
            )
            return

        try:
            event_data = parse_last_change_event(str(last_change_sv.value), SDK_LOGGER)
        except Exception as e:
            SDK_LOGGER.error(
                "Device %s: Error parsing RenderingControl LastChange event: %s. Data: %s",
                self.entity_id,
                e,
                last_change_sv.value,
                exc_info=True,
            )
            raise

        if not any(key in event_data for key in ("Volume", "Mute", "commonevent")):
            self.hass.async_create_task(
                self._async_process_rendering_control_event(str(last_change_sv.value))
            )
            return

        # Update _device's internal state
        if "Volume" in event_data:
            vol_data = event_data["Volume"]
            master_volume_val = None
            if isinstance(vol_data, list):
                master_channel_vol = next(
                    (
                        ch_vol
                        for ch_vol in vol_data
                        if ch_vol.get("channel") == "Master"
                    ),
                    None,
                )
                if master_channel_vol:
                    master_volume_val = master_channel_vol.get("val")
            elif isinstance(vol_data, dict):
                master_volume_val = vol_data.get("val")

            if master_volume_val is not None:
                try:
                    self._device.volume = int(master_volume_val)
                except ValueError:
                    SDK_LOGGER.warning(
                        "Device %s: Invalid volume value from event: %s",
                        self.entity_id,
                        master_volume_val,
                    )

        if "Mute" in event_data:
            mute_data = event_data["Mute"]
            master_mute_val = None
            if isinstance(mute_data, list):
                master_channel_mute = next(
                    (
                        ch_mute
                        for ch_mute in mute_data
                        if ch_mute.get("channel") == "Master"
                    ),
                    None,
                )
                if master_channel_mute:
                    master_mute_val = master_channel_mute.get("val")
            elif isinstance(mute_data, dict):
                master_mute_val = mute_data.get("val")

            if master_mute_val is not None:
                new_mute_state = str(master_mute_val) == "1" or master_mute_val is True
                self._device.is_muted = new_mute_state

        commonevent_str = event_data.get("commonevent")
        if not commonevent_str:
            return

        try:
            commonevent = json.loads(commonevent_str)
            category = commonevent.get("category")
            body = commonevent.get("body", {})

            if category == "bluetooth":
                connected = body.get("connected")
                if connected == 1:
                    self._attr_sound_mode = AudioOutputHwMode.OTHER_OUT.display_name  # type: ignore[attr-defined]

            elif category == "hardware":
                output_mode_val = body.get("output_mode")
                if output_mode_val is not None:
                    try:
                        if (
                            self._attr_unique_id
                            and any(
                                key in self._attr_unique_id
                                for key in AUDIO_AUX_MODE_IDS
                            )
                            and output_mode_val == "AUDIO_OUTPUT_AUX_MODE"
                        ):
                            self._attr_sound_mode = (
                                AudioOutputHwMode.SPEAKER_OUT.display_name  # type: ignore[attr-defined]
                            )
                        else:
                            self._attr_sound_mode = (
                                self.get_display_name_by_command_str(output_mode_val)
                            )

                    except ValueError:
                        SDK_LOGGER.warning(
                            "Device %s: Unknown AudioOutputHwMode value received in hardware event: %s",
                            self.entity_id,
                            output_mode_val,
                        )

        except json.JSONDecodeError as e:
            SDK_LOGGER.debug(f"Failed to parse commonevent JSON: {e}")

        self._update_ha_state_from_sdk_cache()

    def get_display_name_by_command_str(self, command_str: str) -> str | None:
        """Helper to get display name from command string for AudioOutputHwMode."""
        for mode in AudioOutputHwMode:
            if hasattr(mode, "command_str") and mode.command_str == command_str:
                return mode.display_name  # type: ignore[attr-defined]
        return AudioOutputHwMode.OTHER_OUT.display_name  # type: ignore[attr-defined]

    @callback
    def _handle_sdk_play_queue_event(
        self, service: UpnpService, state_variables: list[UpnpStateVariable]
    ) -> None:
        """Handle PlayQueue events from the SDK (if implemented)."""
        SDK_LOGGER.debug(
            "Device %s: Received PlayQueue event: %s", self.entity_id, state_variables
        )
        last_change_sv = next(
            (sv for sv in state_variables if sv.name == "LastChange"), None
        )
        if not last_change_sv or last_change_sv.value is None:
            SDK_LOGGER.debug(
                "Device %s: No LastChange in PlayQueue event or value is None.",
                self.entity_id,
            )
            return

        try:
            event_data = parse_last_change_event(str(last_change_sv.value), SDK_LOGGER)
        except Exception as e:
            SDK_LOGGER.error(
                "Device %s: Error parsing PlayQueue LastChange event: %s. Data: %s",
                self.entity_id,
                e,
                last_change_sv.value,
                exc_info=True,
            )
            raise

        # Update _device's internal state
        if "LoopMode" in event_data:  # Corrected from LoopMode
            loop_mode_val = event_data["LoopMode"]
            try:
                self._device.loop_mode = SDKLoopMode(loop_mode_val)
            except ValueError:
                SDK_LOGGER.warning(
                    "Device %s: Invalid loopmode value (not an integer) from PlayQueue event: %s",
                    self.entity_id,
                    loop_mode_val,
                )

        if "LoopMpde" in event_data:  # Corrected from LoopMpde
            loop_mode_val = event_data["LoopMpde"]
            try:
                self._device.loop_mode = SDKLoopMode(loop_mode_val)
            except ValueError:
                SDK_LOGGER.warning(
                    "Device %s: Invalid loopmode value (not an integer) from PlayQueue event: %s",
                    self.entity_id,
                    loop_mode_val,
                )

        # After updating the _device's internal state, trigger a full HA state update
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

        group_info = wiim_data.controller.get_device_group_info(self._device.udn)
        if group_info and group_info.get("role") == "follower":
            SDK_LOGGER.debug(
                "Device %s: Is a follower. Attempting to synchronize supported features from leader.",
                self.entity_id,
            )
            leader_udn = group_info.get("leader_udn")
            if leader_udn:
                leader_entity = self._get_entity_for_udn(leader_udn)
                if (
                    leader_entity
                    and leader_entity.available
                    and leader_entity._attr_supported_features is not None  # noqa: SLF001
                ):
                    if (
                        self._attr_supported_features
                        != leader_entity._attr_supported_features  # noqa: SLF001
                    ):
                        self._attr_supported_features = (
                            leader_entity._attr_supported_features  # noqa: SLF001
                        )
                        SDK_LOGGER.debug(
                            f"Device {self.entity_id}: Follower features synchronized from leader {leader_entity.entity_id}."
                        )
                        if self.hass and self.entity_id:
                            self.async_write_ha_state()
                else:
                    SDK_LOGGER.debug(
                        f"Device {self.entity_id}: Leader entity {leader_udn} not available or its features not yet set. Setting follower to base features for now."
                    )
                    if self._attr_supported_features != SUPPORT_WIIM_BASE:
                        self._attr_supported_features = SUPPORT_WIIM_BASE
                        if self.hass and self.entity_id:
                            self.async_write_ha_state()
            else:
                SDK_LOGGER.debug(
                    f"Device {self.entity_id}: Follower has no known leader UDN. Setting to base features."
                )
                if self._attr_supported_features != SUPPORT_WIIM_BASE:
                    self._attr_supported_features = SUPPORT_WIIM_BASE
                    if self.hass and self.entity_id:
                        self.async_write_ha_state()
            return

        try:
            if not self._device._http_api:  # noqa: SLF001
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
            # self._attr_supported_features = SUPPORT_WIIM_BASE
            if self.hass and self.entity_id:
                self.async_write_ha_state()
            raise

    def _update_supported_features(self) -> None:
        """Update supported features based on current state."""
        self.hass.async_create_task(self._from_device_update_supported_features())

    @callback
    def _update_group_members_attribute(self) -> None:
        """Helper to update the group_members attribute.

        Also determines if the current entity is a leader or follower.
        """
        if not self.hass:
            return

        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if not wiim_data or not wiim_data.controller:
            current_member_id = self.entity_id if self.entity_id else self._device.udn
            self._attr_group_members = [current_member_id]
            self._is_group_leader = True
            return

        controller = wiim_data.controller

        group_info = controller.get_device_group_info(self._device.udn)

        resolved_group_members = []
        current_role = "standalone"

        if group_info:
            current_role = group_info.get("role", "standalone")
            leader_udn = group_info.get("leader_udn")

            if current_role == "leader":
                group_devices = controller.get_group_members(self._device.udn)
                for sdk_device in group_devices:
                    found_entity_id = None
                    for entity_id, mapped_udn in wiim_data.entity_id_to_udn_map.items():
                        if mapped_udn == sdk_device.udn:
                            found_entity_id = entity_id
                            break
                    if found_entity_id:
                        resolved_group_members.append(found_entity_id)
                    else:
                        SDK_LOGGER.warning(
                            "Could not find HA entity_id for UDN %s in group led by %s.",
                            sdk_device.udn,
                            self.entity_id,
                        )
                        resolved_group_members.append(sdk_device.udn)

            elif current_role == "follower":
                # If this device is a follower, its group members are determined by its leader's group
                if leader_udn:
                    leader_entity = self._get_entity_for_udn(leader_udn)
                    if leader_entity and leader_entity._attr_group_members:  # noqa: SLF001
                        # Follower's group_members should mirror the leader's group_members
                        resolved_group_members = list(leader_entity._attr_group_members)  # noqa: SLF001
                    else:
                        # Fallback: if leader entity not found or its group_members not yet set,
                        # just include self.
                        resolved_group_members = [self.entity_id]
                else:
                    resolved_group_members = [self.entity_id]

            # Ensure the current entity_id is always in its own group_members
            if self.entity_id and self.entity_id not in resolved_group_members:
                resolved_group_members.append(self.entity_id)

        else:  # Not part of any group (standalone)
            resolved_group_members = [self.entity_id]

        # Update leader status
        self._is_group_leader = current_role == "leader"

        # Only update if the list content actually changed to avoid unnecessary state writes
        # Use set comparison for order-independent check
        if self._attr_group_members is None or set(self._attr_group_members) != set(
            resolved_group_members
        ):
            self._attr_group_members = resolved_group_members
            SDK_LOGGER.debug(
                "Device %s: Group members updated to %s. Is leader: %s",
                self.entity_id,
                self._attr_group_members,
                self._is_group_leader,
            )

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
                wiim_data.entities_by_entity_id[self.entity_id] = self
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

                if self.entity_id in wiim_data.entities_by_entity_id:
                    try:
                        del wiim_data.entities_by_entity_id[self.entity_id]
                        SDK_LOGGER.debug(
                            "Removed %s from entities_by_entity_id map", self.entity_id
                        )
                    except KeyError:
                        SDK_LOGGER.debug(
                            "Entity %s not found in entities_by_entity_id map for removal.",
                            self.entity_id,
                        )

        await super().async_will_remove_from_hass()

    async def _async_clear_media_metadata(self) -> None:
        """Helper to clear media-related attributes for this entity."""
        self._attr_media_title = None
        self._attr_media_artist = None
        self._attr_media_album_name = None
        self._attr_media_image_url = None
        self._attr_media_content_id = None
        self._attr_media_content_type = None
        self._attr_media_duration = None
        self._attr_media_position = None
        self._attr_media_position_updated_at = None
        self._device.current_track_info = {}
        self._attr_state = MediaPlayerState.IDLE
        if self.hass and self.entity_id:
            self.async_write_ha_state()
        SDK_LOGGER.debug(f"Entity {self.entity_id}: Media metadata cleared.")

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
        self._device._available = False  # noqa: SLF001
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

                initial_group_members_entities = controller.get_group_members(
                    self._device.udn
                )
                SDK_LOGGER.info(
                    "initial_group_members_entities = %d",
                    len(initial_group_members_entities),
                )
                try:
                    for member_device in initial_group_members_entities:
                        member_ha_entity = self._get_entity_for_udn(member_device.udn)
                        if member_ha_entity:
                            SDK_LOGGER.debug(
                                f"Leader {self.entity_id} going offline: explicitly clearing media metadata for former follower {member_ha_entity.entity_id}"
                            )
                            await member_ha_entity._async_clear_media_metadata()  # noqa: SLF001
                        else:
                            SDK_LOGGER.warning(
                                f"Could not find HA entity for follower WiimDevice {member_device.udn}. Cannot clear its metadata."
                            )
                except Exception as exc:
                    SDK_LOGGER.exception(
                        "for initial_group_members_entities fail: %s", exc
                    )
                    raise
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
            self._attr_volume_level = volume
            if self.hass and self.entity_id:
                self.async_write_ha_state()
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
            self._attr_is_volume_muted = mute
            if self.hass and self.entity_id:
                self.async_write_ha_state()
        except WiimException as e:
            SDK_LOGGER.warning(f"Failed to mute volume on {self.entity_id}: {e}")
            await self._async_handle_critical_error(e)
            raise HomeAssistantError(
                f"Failed to mute volume on {self.entity_id}: {e}"
            ) from e

    async def _redirect_command_to_leader(
        self, method_name: str, *args: Any, **kwargs: Any
    ) -> None:
        """Helper to redirect a command to the group leader."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if not wiim_data or not wiim_data.controller:
            SDK_LOGGER.warning(
                "WiiM controller not available for redirection on %s.", self.entity_id
            )
            raise HomeAssistantError(
                f"WiiM controller not available. Cannot redirect {method_name} command."
            )

        controller = wiim_data.controller
        group_info = controller.get_device_group_info(self._device.udn)

        if group_info and group_info.get("role") == "follower":
            leader_udn = group_info.get("leader_udn")
            if leader_udn:
                leader_entity = self._get_entity_for_udn(leader_udn)
                if leader_entity and leader_entity != self:
                    SDK_LOGGER.info(
                        "Redirecting %s command from follower %s to leader %s.",
                        method_name,
                        self.entity_id,
                        leader_entity.entity_id,
                    )
                    leader_method = getattr(leader_entity, method_name, None)
                    if leader_method and callable(leader_method):
                        await leader_method(*args, **kwargs)
                        return
                    SDK_LOGGER.warning(
                        f"Leader entity {leader_entity.entity_id} does not have method {method_name}."
                    )
                    raise HomeAssistantError(
                        f"Leader does not support {method_name} command."
                    )
                SDK_LOGGER.warning(
                    "Follower %s could not find a valid leader entity (%s) for redirection. Command %s will not be executed.",
                    self.entity_id,
                    leader_udn,
                    method_name,
                )
                raise HomeAssistantError(
                    f"Cannot redirect {method_name} command: Leader not found or invalid."
                )
            SDK_LOGGER.warning(
                "Follower %s has no leader UDN in group info. Command %s will not be executed.",
                self.entity_id,
                method_name,
            )
            raise HomeAssistantError(
                f"Cannot redirect {method_name} command: No leader UDN for follower."
            )

        SDK_LOGGER.warning(
            "Attempted to redirect command %s for a non-follower device %s. This is an internal logic error.",
            method_name,
            self.entity_id,
        )
        raise HomeAssistantError(
            f"Internal error: Command {method_name} redirection called on a non-follower."
        )

    @exception_wrap
    async def async_media_play(self) -> None:
        """Send play command."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if wiim_data and wiim_data.controller:
            group_info = wiim_data.controller.get_device_group_info(self._device.udn)
            if group_info and group_info.get("role") == "follower":
                try:
                    await self._redirect_command_to_leader("async_media_play")
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
            self._attr_state = MediaPlayerState.PLAYING
            # self._update_supported_features()
            if self.hass and self.entity_id:
                self.async_write_ha_state()
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
                    await self._redirect_command_to_leader("async_media_pause")
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
            self._attr_state = MediaPlayerState.PAUSED
            # self._update_supported_features()
            if self.hass and self.entity_id:
                self.async_write_ha_state()
        except WiimException as e:
            SDK_LOGGER.warning(
                f"Failed to execute pause command on {self.entity_id}: {e}"
            )
            await self._async_handle_critical_error(e)
            raise HomeAssistantError(f"Failed to pause on {self.entity_id}: {e}") from e

        await self._sync_device_duration_and_position()

    @exception_wrap
    async def async_media_stop(self) -> None:
        """Send stop command."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if wiim_data and wiim_data.controller:
            group_info = wiim_data.controller.get_device_group_info(self._device.udn)
            if group_info and group_info.get("role") == "follower":
                try:
                    await self._redirect_command_to_leader("async_media_stop")
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
            self._attr_state = MediaPlayerState.IDLE
            # self._update_supported_features()
            if self.hass and self.entity_id:
                self.async_write_ha_state()
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
                    await self._redirect_command_to_leader("async_media_next_track")
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
                    await self._redirect_command_to_leader("async_media_previous_track")
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
                    await self._redirect_command_to_leader("async_media_seek", position)
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
                if not self._device._http_api:  # noqa: SLF001
                    raise HomeAssistantError(
                        f"HTTP API not available for {self._device.name} to play preset."
                    )
                await self._device._http_command_ok(  # noqa: SLF001
                    WiimHttpCommand.PLAY_PRESET, str(preset_number)
                )
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
                if not self._device._http_api:  # noqa: SLF001
                    raise HomeAssistantError(
                        f"HTTP API not available for {self._device.name} to play preset."
                    )
                await self._device._http_command_ok(  # noqa: SLF001
                    WiimHttpCommand.PLAY, url
                )
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

        self._attr_repeat = repeat
        # self._update_supported_features()
        if self.hass and self.entity_id:
            self.async_write_ha_state()

    @exception_wrap
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        sdk_loop_mode_int = self.fromShuffleToInt(shuffle)
        await self._device.async_set_loop_mode(SDKLoopMode(sdk_loop_mode_int))

        self._attr_shuffle = shuffle
        # self._update_supported_features()
        if self.hass and self.entity_id:
            self.async_write_ha_state()

    @exception_wrap
    async def async_select_source(self, source: str) -> None:
        """Select input mode."""
        # await self._device.async_set_play_mode(source)
        try:
            await self._device.async_set_play_mode(source)
            self._attr_source = source

            if self.hass and self.entity_id:
                self.async_write_ha_state()
        except WiimException as e:
            SDK_LOGGER.error(f"Failed to select source on {self.entity_id}: {e}")
            await self._async_handle_critical_error(e)
            raise HomeAssistantError(
                f"Failed to select source on {self.entity_id}: {e}"
            ) from e

    @exception_wrap
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select output mode (e.g., optical, coaxial)."""
        # await self._device.async_set_output_mode(sound_mode)

        try:
            if sound_mode == AudioOutputHwMode.OTHER_OUT.display_name:  # type: ignore[attr-defined]
                if self.hass and self.entity_id:
                    self.async_write_ha_state()
                return
            await self._device.async_set_output_mode(sound_mode)
            self._attr_sound_mode = sound_mode

            if self.hass and self.entity_id:
                self.async_write_ha_state()
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
            # return media_sources_item

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
                # trackSourceQueue = sdk_playlist_tracks["SourceName"]
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
                    # SDK_LOGGER.debug("browse_media: uri=%s, name=%s, image_url=%s", item["uri"], item["name"], item["image_url"])
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

    @exception_wrap
    async def async_play_preset_service(self, preset_number: int) -> None:
        """Service call: Play preset."""
        # This service is usually called internally by play_media for presets
        # but can be exposed directly.
        if not self._device._http_api:  # noqa: SLF001
            raise HomeAssistantError(
                f"HTTP API not available for {self._device.name} to play preset."
            )
        await self._device._http_command_ok(  # noqa: SLF001
            WiimHttpCommand.PLAY_PRESET, str(preset_number)
        )

    @exception_wrap
    async def async_join_players(self, group_members: list[str]) -> None:
        """Join group_members (entity_ids) to the group led by the current player."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if not wiim_data or not wiim_data.controller:
            raise HomeAssistantError("WiiM controller not available.")

        controller = wiim_data.controller
        current_player_udn = self._device.udn

        follower_udns_to_join: list[str] = []
        for member_entity_id in group_members:
            if member_entity_id == self.entity_id:
                SDK_LOGGER.debug("Skipping joining self to group: %s", member_entity_id)
                continue

            follower_udn = wiim_data.entity_id_to_udn_map.get(member_entity_id)
            if not follower_udn:
                SDK_LOGGER.info(
                    "Could not find UDN for entity_id %s in map. Cannot join to group.",
                    member_entity_id,
                )
                continue
            if follower_udn == current_player_udn:
                SDK_LOGGER.debug(
                    "Follower %s is already the leader, skipping join.",
                    member_entity_id,
                )
                continue

            # Check if already in the group or part of another group
            follower_group_info = controller.get_device_group_info(follower_udn)
            if (
                follower_group_info
                and follower_group_info.get("role") == "follower"
                and follower_group_info.get("leader_udn") == current_player_udn
            ):
                SDK_LOGGER.debug(
                    "Follower %s is already in this group, skipping join.",
                    member_entity_id,
                )
                continue

            # If follower is a leader of its own group, it needs to unjoin first
            if follower_group_info and follower_group_info.get("role") == "leader":
                SDK_LOGGER.info(
                    "Follower %s is currently a leader, unjoining it first.",
                    member_entity_id,
                )
                try:
                    await controller.async_ungroup_device(follower_udn)
                    await asyncio.sleep(0.5)
                except WiimException as e:
                    SDK_LOGGER.error(
                        "Failed to unjoin existing group for %s before joining new group: %s",
                        member_entity_id,
                        e,
                    )
                    continue

            follower_udns_to_join.append(follower_udn)

        if not follower_udns_to_join:
            SDK_LOGGER.info(
                "No valid new followers to join for leader %s (UDN: %s)",
                self.entity_id,
                current_player_udn,
            )
            return

        SDK_LOGGER.info(
            "Player %s (leader UDN %s) attempting to group with followers (UDNs: %s)",
            self.entity_id,
            current_player_udn,
            follower_udns_to_join,
        )

        current_leader_info = controller.get_device_group_info(current_player_udn)
        if not current_leader_info or current_leader_info.get("role") != "leader":
            SDK_LOGGER.info(
                "Player %s is not currently a leader. Attempting to make it a leader by ungrouping it first.",
                self.entity_id,
            )
            try:
                await controller.async_ungroup_device(current_player_udn)
                await asyncio.sleep(0.5)
            except WiimException as e:
                SDK_LOGGER.error(
                    "Failed to ungroup self %s before leading a new group: %s",
                    self.entity_id,
                    e,
                )
                raise HomeAssistantError(
                    f"Failed to prepare {self.entity_id} to be a leader."
                ) from e

        for follower_udn in follower_udns_to_join:
            try:
                await controller.async_join_group(current_player_udn, follower_udn)
                SDK_LOGGER.debug(
                    "Successfully sent join command for follower UDN %s to group of leader UDN %s",
                    follower_udn,
                    current_player_udn,
                )
            except WiimException as e:
                SDK_LOGGER.error(
                    "Failed to join follower UDN %s to group of leader UDN %s: %s",
                    follower_udn,
                    current_player_udn,
                    e,
                )

        await asyncio.sleep(2)
        await controller.async_update_multiroom_status(self._device)

        if self.hass:
            self.async_write_ha_state()

    @exception_wrap
    async def async_unjoin_player(self) -> None:
        """Remove this player from any group it is currently in."""
        wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
        if not wiim_data or not wiim_data.controller:
            raise HomeAssistantError("WiiM controller not available.")

        controller = wiim_data.controller
        try:
            SDK_LOGGER.info(
                "Player %s (UDN %s) attempting to unjoin from group.",
                self.entity_id,
                self._device.udn,
            )
            await controller.async_ungroup_device(self._device.udn)
        except WiimException as e:
            SDK_LOGGER.error("Failed to unjoin %s: %s", self._device.name, e)

        await asyncio.sleep(1)
        await controller.async_update_all_multiroom_status()

        if self.hass:
            self.async_write_ha_state()
