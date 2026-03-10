"""Support for WiiM Media Players."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, Concatenate

from async_upnp_client.client import UpnpService, UpnpStateVariable
from wiim.consts import AudioOutputHwMode, InputMode, PlayingStatus as SDKPlayingStatus
from wiim.exceptions import WiimDeviceException, WiimException, WiimRequestException
from wiim.models import WiimGroupRole, WiimRepeatMode
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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import DATA_WIIM, LOGGER, WiimData
from .entity import WiimBaseEntity

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

SDK_TO_HA_REPEAT = {
    WiimRepeatMode.ALL: RepeatMode.ALL,
    WiimRepeatMode.ONE: RepeatMode.ONE,
    WiimRepeatMode.OFF: RepeatMode.OFF,
}

HA_TO_SDK_REPEAT = {
    RepeatMode.ALL: WiimRepeatMode.ALL,
    RepeatMode.ONE: WiimRepeatMode.ONE,
    RepeatMode.OFF: WiimRepeatMode.OFF,
}


def media_player_exception_wrap[
    _WiimMediaPlayerEntityT: "WiimMediaPlayerEntity", **_P, _R
 ](
    func: Callable[Concatenate[_WiimMediaPlayerEntityT, _P], Awaitable[_R]],
) -> Callable[Concatenate[_WiimMediaPlayerEntityT, _P], Awaitable[_R]]:
    """Wrap media player commands to handle SDK exceptions consistently."""

    @wraps(func)
    async def _wrap(
        self: _WiimMediaPlayerEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R:
        try:
            result = await func(self, *args, **kwargs)
        except (WiimDeviceException, WiimRequestException, WiimException) as err:
            LOGGER.warning("%s failed for %s: %s", func.__name__, self.entity_id, err)
            await self._async_handle_critical_error(err)
            raise HomeAssistantError(
                f"{func.__name__} failed for {self.entity_id}"
            ) from err
        except RuntimeError as err:
            LOGGER.warning("%s failed for %s: %s", func.__name__, self.entity_id, err)
            raise HomeAssistantError(
                f"{func.__name__} failed for {self.entity_id}"
            ) from err

        self._update_ha_state_from_sdk_cache()

        return result

    return _wrap


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WiiM media player from a config entry."""

    device: WiimDevice = entry.runtime_data

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
        self.model_name = device.model_name

        self._attr_state = MediaPlayerState.IDLE
        self._attr_media_image_url: str | None = None
        self._attr_media_image_remotely_accessible = True
        self._attr_source_list = list(device.supported_input_modes) or None
        self._attr_shuffle: bool = False
        self._attr_repeat: RepeatMode | str = RepeatMode.OFF
        self._attr_sound_mode_list = list(device.supported_output_modes) or None
        self._attr_supported_features = SUPPORT_WIIM_BASE
        self._supported_features_update_in_flight = False

    @property
    def _wiim_data(self) -> WiimData:
        """Return shared WiiM domain data."""
        return self.hass.data[DATA_WIIM]

    @callback
    def _get_entity_id_for_udn(self, udn: str) -> str | None:
        """Helper to get a WiimMediaPlayerEntity ID by UDN from shared data."""
        for entity_id, stored_udn in self._wiim_data.entity_id_to_udn_map.items():
            if stored_udn == udn:
                return entity_id

        LOGGER.debug("No entity ID found for UDN: %s", udn)
        return None

    def _get_group_snapshot(self):
        """Return the typed group snapshot for the current device, if available."""
        return self._wiim_data.controller.get_group_snapshot(self._device.udn)

    @callback
    def _update_ha_state_from_sdk_cache(self) -> None:
        """Update HA state from SDK's cache/HTTP poll attributes.

        This is the main method for updating this entity's HA attributes.
        Crucially, it also handles propagating metadata to followers if this is a leader.
        """
        LOGGER.debug(
            "Device %s: Updating HA state from SDK cache/HTTP poll",
            self.name or self.unique_id,
        )
        self._attr_available = self._device.available

        if not self._attr_available:
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
            if self._added_to_hass:
                self.async_write_ha_state()
            return

        # Update common attributes first
        self._attr_volume_level = (
            float(self._device.volume) / 100.0
            if self._device.volume is not None
            else None
        )
        self._attr_is_volume_muted = self._device.is_muted
        self._attr_source_list = list(self._device.supported_input_modes) or None
        self._attr_sound_mode_list = list(self._device.supported_output_modes) or None

        # Determine current group role (leader/follower/standalone)
        group_snapshot = self._get_group_snapshot()
        self._is_group_leader = (
            group_snapshot is not None and group_snapshot.role == WiimGroupRole.LEADER
        )

        if self._is_group_leader or (
            group_snapshot is not None
            and group_snapshot.role == WiimGroupRole.STANDALONE
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
                    LOGGER.warning(
                        "Device %s: Unknown play_mode value from SDK: %s",
                        self.unique_id,
                        self._device.play_mode,
                    )
                    self._attr_source = InputMode.WIFI.display_name  # type: ignore[attr-defined]

            # Repeat and Shuffle modes
            loop_state = self._device.loop_state
            self._attr_repeat = SDK_TO_HA_REPEAT[loop_state.repeat]
            self._attr_shuffle = loop_state.shuffle

            # Output Mode
            self._attr_sound_mode = self._device.output_mode

            # Current Track Info / Media Metadata
            if media := self._device.current_media:
                self._attr_media_title = media.title
                self._attr_media_artist = media.artist
                self._attr_media_album_name = media.album
                self._attr_media_image_url = media.image_url
                self._attr_media_content_id = media.uri
                self._attr_media_content_type = MediaType.MUSIC
                self._attr_media_duration = media.duration
                self._attr_media_position = media.position
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

        elif group_snapshot is not None and group_snapshot.role == WiimGroupRole.FOLLOWER:
            # This device is a follower. It should actively pull metadata from its leader.
            leader_udn = group_snapshot.leader_udn
            if leader_udn:
                leader_entity_id = self._get_entity_id_for_udn(leader_udn)
                leader_state = (
                    self.hass.states.get(leader_entity_id) if leader_entity_id else None
                )

                if leader_state and leader_entity_id != self.entity_id:
                    LOGGER.debug(
                        "Follower %s: Actively pulling metadata from leader %s",
                        self.entity_id,
                        leader_entity_id,
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
                    LOGGER.debug(
                        "Follower %s: Leader entity %s not found or is self. Clearing own media metadata",
                        self.entity_id,
                        leader_udn,
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
                LOGGER.debug(
                    "Follower %s: No leader UDN found in group info. Clearing own media metadata",
                    self.entity_id,
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

        if group_snapshot is not None:
            group_members = [
                entity_id
                for udn in group_snapshot.member_udns
                if (entity_id := self._get_entity_id_for_udn(udn)) is not None
            ]
            self._attr_group_members = group_members or None
        else:
            self._attr_group_members = [self.entity_id] if self._added_to_hass else None

        self._update_supported_features()

        if self._added_to_hass:
            self.async_write_ha_state()

    async def _update_output_mode(self) -> None:
        if self._device.supports_http_api:
            self._attr_sound_mode = await self._device.get_audio_output_hw_mode()
        else:
            LOGGER.error(
                "Device %s: HTTP API not available for initial output mode fetch",
                self.entity_id,
            )

    @callback
    def _handle_sdk_general_device_update(self, device: WiimDevice) -> None:
        """Handle general updates from the SDK (e.g., availability, polled data)."""
        LOGGER.debug(
            "Device %s: Received general SDK update from %s",
            self.entity_id,
            device.name,
        )
        if not self._device.available:
            self.hass.async_create_task(
                self._async_handle_critical_error(WiimException("Device offline."))
            )
            return

        async def _wrapped() -> None:
            if self._device.supports_http_api:
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

        LOGGER.debug(
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
                    LOGGER.debug(
                        "Device %s: TransportState is STOPPED. Resetting media position and metadata",
                        self.entity_id,
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
                LOGGER.warning(
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
        LOGGER.debug(
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
        LOGGER.debug(
            "Device %s: Received PlayQueue event: %s", self.entity_id, state_variables
        )
        self._update_ha_state_from_sdk_cache()

    def _update_support_features(self, features: MediaPlayerEntityFeature) -> None:
        """Update entity supported features and write state if changed."""
        if self._attr_supported_features != features:
            self._attr_supported_features = features
            if self._added_to_hass:
                self.async_write_ha_state()

    async def _sync_follower_features(self, wiim_data: WiimData) -> bool:
        """Synchronize features if this device is a follower."""
        group_snapshot = wiim_data.controller.get_group_snapshot(self._device.udn)
        if group_snapshot is None or group_snapshot.role != WiimGroupRole.FOLLOWER:
            return False

        leader_entity_id = self._get_entity_id_for_udn(group_snapshot.leader_udn)
        leader_state = self.hass.states.get(leader_entity_id) if leader_entity_id else None
        if leader_state and leader_entity_id != self.entity_id:
            leader_features = leader_state.attributes.get("supported_features")
            if leader_features is not None:
                self._update_support_features(leader_features)
                LOGGER.debug(
                    "Device %s: Follower features synchronized from leader %s",
                    self.entity_id,
                    leader_entity_id,
                )
                return True

        # fallback to base features
        self._update_support_features(SUPPORT_WIIM_BASE)
        LOGGER.debug("Device %s: Follower set to base features", self.entity_id)
        return True

    async def _from_device_update_supported_features(self) -> None:
        """Fetches media info from the device to dynamically update supported features.

        This method is asynchronous and makes a network call.
        """
        if await self._sync_follower_features(self._wiim_data):
            return

        try:
            capabilities = await self._device.async_get_transport_capabilities()

            current_features = SUPPORT_WIIM_BASE
            if not self._device.supports_http_api:
                current_features &= ~MediaPlayerEntityFeature.BROWSE_MEDIA

            if not capabilities.can_next:
                current_features &= ~MediaPlayerEntityFeature.NEXT_TRACK
            if not capabilities.can_previous:
                current_features &= ~MediaPlayerEntityFeature.PREVIOUS_TRACK

            loop_mode_flags = (
                MediaPlayerEntityFeature.REPEAT_SET
                | MediaPlayerEntityFeature.SHUFFLE_SET
            )

            if not capabilities.can_repeat:
                current_features &= ~MediaPlayerEntityFeature.REPEAT_SET
            if not capabilities.can_shuffle:
                current_features &= ~MediaPlayerEntityFeature.SHUFFLE_SET
            if capabilities.can_repeat and capabilities.can_shuffle:
                current_features |= loop_mode_flags

            if self._attr_supported_features != current_features:
                self._attr_supported_features = current_features
                LOGGER.debug(
                    "Device %s: Updated supported features to %s",
                    self.entity_id,
                    current_features,
                )
                if self._added_to_hass:
                    self.async_write_ha_state()

        except WiimRequestException as e:
            LOGGER.warning(
                "Device %s: Failed to fetch transport capabilities for supported features: %s",
                self.entity_id,
                e,
            )
            if self._added_to_hass:
                self.async_write_ha_state()
        except (AttributeError, RuntimeError) as err:
            LOGGER.error(
                "Device %s: Unexpected error in _from_device_update_supported_features: %s",
                self.entity_id,
                err,
            )
            if self._added_to_hass:
                self.async_write_ha_state()

    def _update_supported_features(self) -> None:
        """Update supported features based on current state."""
        if not self.hass:
            return

        # Avoid parallel MEDIA_INFO request.
        if self._supported_features_update_in_flight:
            return

        self._supported_features_update_in_flight = True

        async def _refresh_supported_features() -> None:
            try:
                await self._from_device_update_supported_features()
            finally:
                self._supported_features_update_in_flight = False

        self.hass.async_create_task(_refresh_supported_features())

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
            LOGGER.debug(
                "Entity %s registered callbacks with WiimDevice %s",
                self.entity_id,
                self._device.name,
            )
            if self._device.supports_http_api:
                await self._update_output_mode()

            if self.entity_id:
                self._wiim_data.entity_id_to_udn_map[self.entity_id] = self._device.udn
                LOGGER.debug(
                    "Added %s (UDN: %s) to entity maps in hass.data",
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
            LOGGER.debug(
                "Entity %s unregistered callbacks from WiimDevice %s",
                self.entity_id,
                self._device.name,
            )
            await self._device.disconnect()

        # Remove entity_id from the global map
        if self.entity_id in self._wiim_data.entity_id_to_udn_map:
            del self._wiim_data.entity_id_to_udn_map[self.entity_id]
            LOGGER.debug("Removed %s from entity_id_to_udn_map", self.entity_id)

        await super().async_will_remove_from_hass()

    async def _async_handle_critical_error(self, e: WiimException) -> None:
        """Handle critical communication errors, marking device unavailable and cleaning up."""
        LOGGER.warning(
            "Device %s encountered a critical communication error: %s",
            self.entity_id,
            e,
        )

        if not self._device.available:
            return

        LOGGER.info(
            "Device %s is now considered offline. Disconnecting UPnP subscriptions",
            self.entity_id,
        )
        self._device.set_available(False)
        controller = self._wiim_data.controller
        group_snapshot = controller.get_group_snapshot(self._device.udn)

        if group_snapshot is not None:
            if group_snapshot.role == WiimGroupRole.LEADER:
                LOGGER.info(
                    "Device %s was a leader. Attempting to ungroup all its followers",
                    self.entity_id,
                )

                # Cannot clear followers metadata directly anymore as we don't have access to their entities.
                # Followers must handle leader unavailability themselves.
            elif group_snapshot.role == WiimGroupRole.FOLLOWER:
                LOGGER.info(
                    "Device %s was a follower. Attempting to unjoin from its group",
                    self.entity_id,
                )

        await controller.async_update_all_multiroom_status()

        self._update_ha_state_from_sdk_cache()

    @media_player_exception_wrap
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0-1."""
        await self._device.async_set_volume(int(volume * 100))

    @media_player_exception_wrap
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self._device.async_set_mute(mute)

    async def _call_leader_service(self, service_name: str, **kwargs: Any) -> None:
        """Helper to call a media_player service on the group leader."""
        group_snapshot = self._get_group_snapshot()
        if group_snapshot is None or group_snapshot.role != WiimGroupRole.FOLLOWER:
            raise HomeAssistantError(
                f"Internal error: {service_name} redirection called for non-follower {self.entity_id}."
            )

        leader_entity_id = self._get_entity_id_for_udn(group_snapshot.command_target_udn)
        if leader_entity_id is None or leader_entity_id == self.entity_id:
            raise HomeAssistantError(
                f"Cannot redirect {service_name}: leader entity for {self.entity_id} was not found."
            )

        LOGGER.info(
            "Redirecting %s command from follower %s to leader %s",
            service_name,
            self.entity_id,
            leader_entity_id,
        )
        await self.hass.services.async_call(
            "media_player",
            service_name,
            {"entity_id": leader_entity_id, **kwargs},
            blocking=True,
            context=self._context,
        )

    async def _async_redirect_to_leader(
        self, service_name: str, **kwargs: Any
    ) -> bool:
        """Redirect a command to the leader when this entity is a follower."""
        group_snapshot = self._get_group_snapshot()
        if group_snapshot is None or group_snapshot.role != WiimGroupRole.FOLLOWER:
            return False

        try:
            await self._call_leader_service(service_name, **kwargs)
        except HomeAssistantError:
            if self._attr_available:
                await self._async_handle_critical_error(
                    WiimException(f"Leader unavailable for {service_name}")
                )
            raise

        return True

    @media_player_exception_wrap
    async def async_media_play(self) -> None:
        """Send play command."""
        if await self._async_redirect_to_leader("media_play"):
            return

        await self._device.async_play()

    @media_player_exception_wrap
    async def async_media_pause(self) -> None:
        """Send pause command."""
        if await self._async_redirect_to_leader("media_pause"):
            return

        await self._device.async_pause()
        await self._device.sync_device_duration_and_position()

    @media_player_exception_wrap
    async def async_media_stop(self) -> None:
        """Send stop command."""
        if await self._async_redirect_to_leader("media_stop"):
            return

        await self._device.async_stop()

    @media_player_exception_wrap
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if await self._async_redirect_to_leader("media_next_track"):
            return

        await self._device.async_next()

    @media_player_exception_wrap
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        if await self._async_redirect_to_leader("media_previous_track"):
            return

        await self._device.async_previous()

    @media_player_exception_wrap
    async def async_media_seek(self, position: float) -> None:
        """Seek to a specific position in the track."""
        if await self._async_redirect_to_leader("media_seek", seek_position=position):
            return

        await self._device.async_seek(int(position))

    @media_player_exception_wrap
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        LOGGER.debug(
            "async_play_media: type=%s, id=%s, kwargs=%s", media_type, media_id, kwargs
        )

        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url

            url = async_process_play_media_url(self.hass, media_id)
            LOGGER.debug("HTTP media_type for play_media: %s", url)
            await self._device.play_url(url)
            self._attr_state = MediaPlayerState.PLAYING
        elif media_type in {MediaType.MUSIC, MEDIA_TYPE_WIIM_LIBRARY}:
            if not media_id.isdigit():
                raise ServiceValidationError(f"Invalid preset ID: {media_id}")

            preset_number = int(media_id)
            await self._device.play_preset(preset_number)
            self._attr_media_content_id = f"wiim_preset_{preset_number}"
            self._attr_media_content_type = MediaType.PLAYLIST
            self._attr_state = MediaPlayerState.PLAYING
        elif media_type == MediaType.TRACK:
            if not media_id.isdigit():
                raise ServiceValidationError(
                    f"Invalid media_id: {media_id}. Expected a valid track index."
                )

            track_index = int(media_id)
            await self._device.async_play_queue_with_index(track_index)
            self._attr_media_content_id = f"wiim_track_{track_index}"
            self._attr_media_content_type = MediaType.TRACK
            self._attr_state = MediaPlayerState.PLAYING
        else:
            LOGGER.warning("Unsupported media_type for play_media: %s", media_type)
            raise ServiceValidationError(f"Unsupported media type: {media_type}")

    @media_player_exception_wrap
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        sdk_repeat = HA_TO_SDK_REPEAT[repeat]
        await self._device.async_set_loop_mode(
            self._device.build_loop_mode(sdk_repeat, self._attr_shuffle)
        )

    @media_player_exception_wrap
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        await self._device.async_set_loop_mode(
            self._device.build_loop_mode(
                HA_TO_SDK_REPEAT[self._attr_repeat],
                shuffle,
            )
        )

    @media_player_exception_wrap
    async def async_select_source(self, source: str) -> None:
        """Select input mode."""
        await self._device.async_set_play_mode(source)

    @media_player_exception_wrap
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select output mode (e.g., optical, coaxial)."""
        if sound_mode == AudioOutputHwMode.OTHER_OUT.display_name:  # type: ignore[attr-defined]
            return

        await self._device.async_set_output_mode(sound_mode)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement media Browse helper."""
        LOGGER.debug(
            "Browsing media: content_type=%s, content_id=%s",
            media_content_type,
            media_content_id,
        )

        if media_content_id is not None and media_source.is_media_source_id(
            media_content_id
        ):
            return await media_source.async_browse_media(
                self.hass,
                media_content_id,
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
                None,
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

        if media_content_id == MEDIA_CONTENT_ID_FAVORITES:
            sdk_favorites = await self._device.async_get_presets()
            favorites_items = [
                BrowseMedia(
                    media_class=MediaClass.PLAYLIST,
                    media_content_id=str(item.preset_id),
                    media_content_type=MediaType.MUSIC,
                    title=item.title,
                    can_play=True,
                    can_expand=False,
                    thumbnail=item.image_url,
                )
                for item in sdk_favorites
            ]

            return BrowseMedia(
                media_class=MediaClass.PLAYLIST,
                media_content_id=MEDIA_CONTENT_ID_FAVORITES,
                media_content_type=MediaType.PLAYLIST,
                title="Presets",
                can_play=False,
                can_expand=True,
                children=favorites_items,
            )

        if media_content_id == MEDIA_CONTENT_ID_PLAYLISTS:
            queue_snapshot = await self._device.async_get_queue_snapshot()
            if not queue_snapshot.is_active:
                return BrowseMedia(
                    media_class=MediaClass.PLAYLIST,
                    media_content_id=MEDIA_CONTENT_ID_PLAYLISTS,
                    media_content_type=MediaType.PLAYLIST,
                    title="Queue",
                    can_play=False,
                    can_expand=True,
                    children=[],
                )

            playlist_track_items = [
                BrowseMedia(
                    media_class=MediaClass.TRACK,
                    media_content_id=str(item.queue_index),
                    media_content_type=MediaType.TRACK,
                    title=item.title,
                    can_play=True,
                    can_expand=False,
                    thumbnail=item.image_url,
                )
                for item in queue_snapshot.items
            ]

            return BrowseMedia(
                media_class=MediaClass.PLAYLIST,
                media_content_id=MEDIA_CONTENT_ID_PLAYLISTS,
                media_content_type=MediaType.PLAYLIST,
                title="Queue",
                can_play=False,
                can_expand=True,
                children=playlist_track_items,
            )

        LOGGER.warning(
            "Unhandled browse_media request: content_type=%s, content_id=%s",
            media_content_type,
            media_content_id,
        )
        raise BrowseError(f"Invalid browse path: {media_content_id}")
