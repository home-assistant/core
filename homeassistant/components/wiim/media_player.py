"""Support for WiiM Media Players."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from contextlib import suppress
from functools import wraps
from hashlib import sha1
from http import HTTPStatus
from typing import Any, Concatenate
from urllib.parse import urlparse

import aiohttp
from async_upnp_client.client import UpnpService, UpnpStateVariable
from wiim.consts import PlayingStatus as SDKPlayingStatus
from wiim.exceptions import WiimDeviceException, WiimException, WiimRequestException
from wiim.models import (
    WiimGroupRole,
    WiimGroupSnapshot,
    WiimRepeatMode,
    WiimTransportCapabilities,
)
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
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import DATA_WIIM, LOGGER, WiimConfigEntry
from .entity import WiimBaseEntity
from .models import WiimData

MEDIA_TYPE_WIIM_LIBRARY = "wiim_library"
MEDIA_CONTENT_ID_ROOT = "library_root"
MEDIA_CONTENT_ID_FAVORITES = (
    f"{MEDIA_TYPE_WIIM_LIBRARY}/{MEDIA_CONTENT_ID_ROOT}/favorites"
)
MEDIA_CONTENT_ID_PLAYLISTS = (
    f"{MEDIA_TYPE_WIIM_LIBRARY}/{MEDIA_CONTENT_ID_ROOT}/playlists"
)
MEDIA_IMAGE_FETCH_TIMEOUT = aiohttp.ClientTimeout(total=10)


def _group_member_state_signal(member_udn: str) -> str:
    """Return the dispatcher signal for a grouped member state refresh."""
    return f"wiim_group_member_state_{member_udn}"


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
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.GROUPING
)


def media_player_exception_wrap[
    _WiimMediaPlayerEntityT: "WiimMediaPlayerEntity",
    **_P,
    _R,
](
    func: Callable[Concatenate[_WiimMediaPlayerEntityT, _P], Awaitable[_R]],
) -> Callable[Concatenate[_WiimMediaPlayerEntityT, _P], Coroutine[Any, Any, _R]]:
    """Wrap media player commands to handle SDK exceptions consistently."""

    @wraps(func)
    async def _wrap(
        self: _WiimMediaPlayerEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R:
        try:
            result = await func(self, *args, **kwargs)
        except (WiimDeviceException, WiimRequestException, WiimException) as err:
            await self._async_handle_critical_error(err)
            raise HomeAssistantError(
                f"{func.__name__} failed for {self.entity_id}"
            ) from err
        except RuntimeError as err:
            raise HomeAssistantError(
                f"{func.__name__} failed for {self.entity_id}"
            ) from err

        self._update_ha_state_from_sdk_cache()

        return result

    return _wrap


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WiimConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WiiM media player from a config entry."""
    async_add_entities([WiimMediaPlayerEntity(entry.runtime_data, entry)])


class WiimMediaPlayerEntity(WiimBaseEntity, MediaPlayerEntity):
    """Representation of a WiiM media player."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_media_image_remotely_accessible = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(self, device: WiimDevice, entry: WiimConfigEntry) -> None:
        """Initialize the WiiM entity."""
        super().__init__(device)
        self._entry = entry

        self._attr_unique_id = device.udn
        self._attr_source_list = list(device.supported_input_modes) or None
        self._attr_shuffle: bool = False
        self._attr_repeat = RepeatMode.OFF
        self._transport_capabilities: WiimTransportCapabilities | None = None
        self._supported_features_update_in_flight = False

    @property
    def _wiim_data(self) -> WiimData:
        """Return shared WiiM domain data."""
        return self.hass.data[DATA_WIIM]

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the features supported by the current device state."""
        features = SUPPORT_WIIM_BASE
        if self._transport_capabilities is None:
            return features

        if self._transport_capabilities.can_next:
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if self._transport_capabilities.can_previous:
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        if self._transport_capabilities.can_repeat:
            features |= MediaPlayerEntityFeature.REPEAT_SET
        if self._transport_capabilities.can_shuffle:
            features |= MediaPlayerEntityFeature.SHUFFLE_SET

        return features

    @callback
    def _get_entity_id_for_udn(self, udn: str) -> str | None:
        """Helper to get a WiimMediaPlayerEntity ID by UDN from shared data."""
        for entity_id, stored_udn in self._wiim_data.entity_id_to_udn_map.items():
            if stored_udn == udn:
                return entity_id

        LOGGER.debug("No entity ID found for UDN: %s", udn)
        return None

    def _get_group_snapshot(self) -> WiimGroupSnapshot:
        """Return the typed group snapshot for the current device."""
        return self._wiim_data.controller.get_group_snapshot(self._device.udn)

    @property
    def _metadata_device(self) -> WiimDevice:
        """Return the device whose metadata should back this entity."""
        group_snapshot = self._get_group_snapshot()
        if group_snapshot.role != WiimGroupRole.FOLLOWER:
            return self._device

        return self._wiim_data.controller.get_device(group_snapshot.leader_udn)

    @callback
    def _is_local_https_media_image(self, url: str) -> bool:
        """Return True if the media image is served by the current metadata device over HTTPS."""
        parsed_url = urlparse(url)
        if parsed_url.scheme != "https" or not parsed_url.hostname:
            return False

        metadata_device = self._metadata_device
        valid_hosts = {
            host
            for host in (
                metadata_device.ip_address,
                urlparse(metadata_device.presentation_url).hostname
                if metadata_device.presentation_url
                else None,
                urlparse(metadata_device.http_api_url).hostname
                if metadata_device.http_api_url
                else None,
            )
            if host
        }
        return parsed_url.hostname in valid_hosts

    @callback
    def _clear_media_metadata(self) -> None:
        """Clear media metadata attributes."""
        self._attr_media_title = None
        self._attr_media_artist = None
        self._attr_media_album_name = None
        self._attr_media_image_url = None
        self._attr_media_image_hash = None
        self._attr_media_content_id = None
        self._attr_media_content_type = None
        self._attr_media_duration = None
        self._attr_media_position = None
        self._attr_media_position_updated_at = None

    @callback
    def _set_media_image_hash(
        self,
        *,
        image_url: str | None,
        media_uri: str | None,
        title: str | None,
        artist: str | None,
        album: str | None,
    ) -> None:
        """Set a cache-busting media image hash for Home Assistant.

        Some WiiM sources reuse the same artwork URL across tracks, so the
        default HA URL-based hash is not sufficient to invalidate the image cache.
        """
        if not image_url:
            self._attr_media_image_hash = None
            return

        digest_source = "|".join(
            value or "" for value in (image_url, media_uri, title, artist, album)
        )
        self._attr_media_image_hash = sha1(
            digest_source.encode("utf-8"), usedforsecurity=False
        ).hexdigest()

    @callback
    def _get_command_target_device(self, action_name: str) -> WiimDevice:
        """Return the device that should receive a grouped playback command."""
        group_snapshot = self._get_group_snapshot()
        if group_snapshot.role != WiimGroupRole.FOLLOWER:
            return self._device

        target_device = self._wiim_data.controller.get_device(
            group_snapshot.command_target_udn
        )

        LOGGER.info(
            "Routing %s command from follower %s to leader %s",
            action_name,
            self.entity_id,
            target_device.udn,
        )
        return target_device

    @callback
    def _async_handle_group_member_state_refresh(self) -> None:
        """Refresh follower state when the group leader pushes an update."""
        group_snapshot = self._get_group_snapshot()
        if group_snapshot.role != WiimGroupRole.FOLLOWER:
            LOGGER.debug(
                "Ignoring group member refresh for %s because role is %s",
                self.entity_id,
                group_snapshot.role,
            )
            return

        LOGGER.debug(
            "Follower %s received propagated group update from leader %s",
            self.entity_id,
            group_snapshot.leader_udn,
        )
        self._update_ha_state_from_sdk_cache()

    @callback
    def _async_propagate_group_state_update(
        self, group_snapshot: WiimGroupSnapshot
    ) -> None:
        """Notify grouped followers to refresh from the leader's latest cache."""
        if group_snapshot.role != WiimGroupRole.LEADER:
            return

        for member_udn in group_snapshot.member_udns:
            if member_udn == self._device.udn:
                continue

            LOGGER.debug(
                "Leader %s propagating grouped state refresh to follower %s",
                self.entity_id,
                member_udn,
            )
            async_dispatcher_send(self.hass, _group_member_state_signal(member_udn))

    @callback
    def _update_ha_state_from_sdk_cache(
        self,
        *,
        write_state: bool = True,
        update_supported_features: bool = True,
    ) -> None:
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
            self._clear_media_metadata()
            self._attr_source = None
            self._transport_capabilities = None
            if write_state:
                self.async_write_ha_state()
            return

        # Update common attributes first
        self._attr_volume_level = self._device.volume / 100
        self._attr_is_volume_muted = self._device.is_muted
        self._attr_source_list = list(self._device.supported_input_modes) or None

        # Determine current group role (leader/follower/standalone)
        group_snapshot = self._get_group_snapshot()

        metadata_device = self._metadata_device
        if group_snapshot.role == WiimGroupRole.FOLLOWER:
            LOGGER.debug(
                "Follower %s: Actively pulling metadata from leader %s",
                self.entity_id,
                metadata_device.udn,
            )

        if metadata_device.playing_status is not None:
            self._attr_state = SDK_TO_HA_STATE.get(
                metadata_device.playing_status, MediaPlayerState.IDLE
            )

        if metadata_device.play_mode is not None:
            self._attr_source = metadata_device.play_mode

        loop_state = metadata_device.loop_state
        self._attr_repeat = RepeatMode(loop_state.repeat)
        self._attr_shuffle = loop_state.shuffle

        if media := metadata_device.current_media:
            self._attr_media_title = media.title
            self._attr_media_artist = media.artist
            self._attr_media_album_name = media.album
            self._attr_media_image_url = media.image_url
            self._set_media_image_hash(
                image_url=media.image_url,
                media_uri=media.uri,
                title=media.title,
                artist=media.artist,
                album=media.album,
            )
            self._attr_media_content_id = media.uri
            self._attr_media_content_type = MediaType.MUSIC
            self._attr_media_duration = media.duration
            if self._attr_media_position != media.position:
                self._attr_media_position = media.position
                self._attr_media_position_updated_at = utcnow()
        else:
            self._clear_media_metadata()

        group_members = [
            entity_id
            for udn in group_snapshot.member_udns
            if (entity_id := self._get_entity_id_for_udn(udn)) is not None
        ]
        self._attr_group_members = group_members or ([self.entity_id])

        if update_supported_features:
            self._async_schedule_update_supported_features()

        if write_state:
            self.async_write_ha_state()
            self._async_propagate_group_state_update(group_snapshot)

    @callback
    def _handle_sdk_general_device_update(self, device: WiimDevice) -> None:
        """Handle general updates from the SDK (e.g., availability, polled data)."""
        LOGGER.debug(
            "Device %s: Received general SDK update from %s",
            self.entity_id,
            device.name,
        )
        if not self._device.available:
            self._update_ha_state_from_sdk_cache()
            self._entry.async_create_background_task(
                self.hass,
                self._async_handle_critical_error(WiimException("Device offline.")),
                name=f"wiim_{self.entity_id}_critical_error",
            )
            return

        async def _wrapped() -> None:
            await self._device.ensure_subscriptions()
            self._update_ha_state_from_sdk_cache()

        if self._device.supports_http_api:
            self._entry.async_create_background_task(
                self.hass,
                _wrapped(),
                name=f"wiim_{self.entity_id}_general_update",
            )
        else:
            self._update_ha_state_from_sdk_cache()

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
            except ValueError:
                LOGGER.warning(
                    "Device %s: Unknown TransportState from event: %s",
                    self.entity_id,
                    sdk_status_str,
                )
            else:
                if sdk_status == SDKPlayingStatus.STOPPED:
                    LOGGER.debug(
                        "Device %s: TransportState is STOPPED. Resetting media position and metadata",
                        self.entity_id,
                    )
                    self._attr_media_position_updated_at = None
                    self._attr_media_duration = None
                    self._attr_media_position = None
                elif sdk_status in {SDKPlayingStatus.PAUSED, SDKPlayingStatus.PLAYING}:
                    self._entry.async_create_background_task(
                        self.hass,
                        self._device.sync_device_duration_and_position(),
                        name=f"wiim_{self.entity_id}_sync_position",
                    )

        self._update_ha_state_from_sdk_cache()

    @callback
    def _handle_sdk_refresh_event(
        self, _service: UpnpService, state_variables: list[UpnpStateVariable]
    ) -> None:
        """Handle SDK events that only require a state refresh."""
        LOGGER.debug(
            "Device %s: Received SDK refresh event: %s", self.entity_id, state_variables
        )
        self._update_ha_state_from_sdk_cache()

    async def _async_get_transport_capabilities_for_device(
        self, device: WiimDevice
    ) -> WiimTransportCapabilities | None:
        """Return transport capabilities for a device."""
        try:
            return await device.async_get_transport_capabilities()
        except WiimRequestException as err:
            LOGGER.warning(
                "Device %s: Failed to fetch transport capabilities: %s",
                device.udn,
                err,
            )
            return None
        except RuntimeError as err:
            LOGGER.error(
                "Device %s: Unexpected error in transport capability detection: %s",
                device.udn,
                err,
            )
            return None

    async def _from_device_update_supported_features(
        self, *, write_state: bool = True
    ) -> None:
        """Fetches media info from the device to dynamically update supported features.

        This method is asynchronous and makes a network call.
        """
        metadata_device = self._metadata_device
        previous_capabilities = self._transport_capabilities
        if (
            transport_capabilities
            := await self._async_get_transport_capabilities_for_device(metadata_device)
        ) is not None:
            if self._transport_capabilities != transport_capabilities:
                self._transport_capabilities = transport_capabilities
                LOGGER.debug(
                    "Device %s: Updated transport capabilities to %s",
                    self.entity_id,
                    transport_capabilities,
                )
        elif (
            metadata_device is not self._device
            and self._transport_capabilities is not None
        ):
            self._transport_capabilities = None
            LOGGER.debug(
                "Device %s: Follower transport capabilities unavailable, using base features",
                self.entity_id,
            )

        if write_state and self._transport_capabilities != previous_capabilities:
            self.async_write_ha_state()

    @callback
    def _async_schedule_update_supported_features(self) -> None:
        """Update supported features based on current state."""
        # Avoid parallel MEDIA_INFO request.
        if self._supported_features_update_in_flight:
            return

        self._supported_features_update_in_flight = True

        async def _refresh_supported_features() -> None:
            try:
                await self._from_device_update_supported_features()
            finally:
                self._supported_features_update_in_flight = False

        self._entry.async_create_background_task(
            self.hass,
            _refresh_supported_features(),
            name=f"wiim_{self.entity_id}_refresh_supported_features",
        )

    @callback
    def _async_registry_updated(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Keep the entity-to-UDN map in sync with entity registry updates."""
        if (
            event.data["action"] == "update"
            and (old_entity_id := event.data.get("old_entity_id"))
            and old_entity_id != (entity_id := event.data["entity_id"])
        ):
            self._wiim_data.entity_id_to_udn_map.pop(old_entity_id, None)
            self._wiim_data.entity_id_to_udn_map[entity_id] = self._device.udn

        super()._async_registry_updated(event)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._wiim_data.entity_id_to_udn_map[self.entity_id] = self._device.udn
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                _group_member_state_signal(self._device.udn),
                self._async_handle_group_member_state_refresh,
            )
        )
        LOGGER.debug(
            "Added %s (UDN: %s) to entity maps in hass.data",
            self.entity_id,
            self._device.udn,
        )

        await self._from_device_update_supported_features(write_state=False)
        self._update_ha_state_from_sdk_cache(
            write_state=False, update_supported_features=False
        )
        self._device.general_event_callback = self._handle_sdk_general_device_update
        self._device.av_transport_event_callback = self._handle_sdk_av_transport_event
        self._device.rendering_control_event_callback = self._handle_sdk_refresh_event
        self._device.play_queue_event_callback = self._handle_sdk_refresh_event
        LOGGER.debug(
            "Entity %s registered callbacks with WiimDevice %s",
            self.entity_id,
            self._device.name,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from Home Assistant."""
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
        self._wiim_data.entity_id_to_udn_map.pop(self.entity_id, None)
        LOGGER.debug("Removed %s from entity_id_to_udn_map", self.entity_id)

        await super().async_will_remove_from_hass()

    async def _async_handle_critical_error(self, error: WiimException) -> None:
        """Handle communication failures by marking the device unavailable."""
        if self._device.available:
            LOGGER.info(
                "Lost connection to WiiM device %s: %s",
                self.entity_id,
                error,
            )
            self._device.set_available(False)
            self._update_ha_state_from_sdk_cache()

        await self._wiim_data.controller.async_update_all_multiroom_status()

    @media_player_exception_wrap
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0-1."""
        await self._device.async_set_volume(round(volume * 100))

    @media_player_exception_wrap
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self._device.async_set_mute(mute)

    @media_player_exception_wrap
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._get_command_target_device("media_play").async_play()

    @media_player_exception_wrap
    async def async_media_pause(self) -> None:
        """Send pause command."""
        target_device = self._get_command_target_device("media_pause")
        await target_device.async_pause()
        await target_device.sync_device_duration_and_position()

    @media_player_exception_wrap
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._get_command_target_device("media_stop").async_stop()

    @media_player_exception_wrap
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._get_command_target_device("media_next_track").async_next()

    @media_player_exception_wrap
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._get_command_target_device("media_previous_track").async_previous()

    @media_player_exception_wrap
    async def async_media_seek(self, position: float) -> None:
        """Seek to a specific position in the track."""
        await self._get_command_target_device("media_seek").async_seek(int(position))

    @media_player_exception_wrap
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        LOGGER.debug(
            "async_play_media: type=%s, id=%s, kwargs=%s", media_type, media_id, kwargs
        )
        target_device = self._get_command_target_device("play_media")

        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            await self._async_play_url(target_device, play_item.url)
        elif media_type == MEDIA_TYPE_WIIM_LIBRARY:
            if not media_id.isdigit():
                raise ServiceValidationError(f"Invalid preset ID: {media_id}")

            preset_number = int(media_id)
            await target_device.play_preset(preset_number)
            self._attr_media_content_id = f"wiim_preset_{preset_number}"
            self._attr_media_content_type = MediaType.PLAYLIST
            self._attr_state = MediaPlayerState.PLAYING
        elif media_type == MediaType.MUSIC:
            if media_id.isdigit():
                preset_number = int(media_id)
                await target_device.play_preset(preset_number)
                self._attr_media_content_id = f"wiim_preset_{preset_number}"
                self._attr_media_content_type = MediaType.PLAYLIST
                self._attr_state = MediaPlayerState.PLAYING
            else:
                await self._async_play_url(target_device, media_id)
        elif media_type == MediaType.URL:
            await self._async_play_url(target_device, media_id)
        elif media_type == MediaType.TRACK:
            if not media_id.isdigit():
                raise ServiceValidationError(
                    f"Invalid media_id: {media_id}. Expected a valid track index."
                )

            track_index = int(media_id)
            await target_device.async_play_queue_with_index(track_index)
            self._attr_media_content_id = f"wiim_track_{track_index}"
            self._attr_media_content_type = MediaType.TRACK
            self._attr_state = MediaPlayerState.PLAYING
        else:
            raise ServiceValidationError(f"Unsupported media type: {media_type}")

    async def _async_play_url(self, target_device: WiimDevice, media_id: str) -> None:
        """Play a direct media URL on the target device."""
        if not target_device.supports_http_api:
            raise ServiceValidationError(
                "Direct URL playback is not supported on this device"
            )

        url = async_process_play_media_url(self.hass, media_id)
        LOGGER.debug("HTTP media_type for play_media: %s", url)
        await target_device.play_url(url)
        self._attr_state = MediaPlayerState.PLAYING

    @media_player_exception_wrap
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        target_device = self._get_command_target_device("repeat_set")
        await target_device.async_set_loop_mode(
            target_device.build_loop_mode(WiimRepeatMode(repeat), self._attr_shuffle)
        )

    @media_player_exception_wrap
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        repeat = self._attr_repeat or WiimRepeatMode.OFF
        target_device = self._get_command_target_device("shuffle_set")
        await target_device.async_set_loop_mode(
            target_device.build_loop_mode(WiimRepeatMode(repeat), shuffle)
        )

    @media_player_exception_wrap
    async def async_select_source(self, source: str) -> None:
        """Select input mode."""
        await self._get_command_target_device("select_source").async_set_play_mode(
            source
        )

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Fetch the current media image.

        Bypass HA's URL-only image cache for device-local HTTPS artwork so
        same-URL images can still refresh when the media metadata changes.
        """
        if (url := self.media_image_url) is None:
            return None, None

        if not self._is_local_https_media_image(url):
            return await super().async_get_media_image()

        content, content_type = None, None
        websession = async_get_clientsession(self.hass)
        with suppress(TimeoutError, aiohttp.ClientError):
            async with websession.get(
                url,
                ssl=False,
                timeout=MEDIA_IMAGE_FETCH_TIMEOUT,
            ) as response:
                if response.status == HTTPStatus.OK:
                    content = await response.read()
                    if response.headers.get("Content-Type"):
                        content_type = response.headers["Content-Type"].split(";")[0]

        if content is None:
            LOGGER.debug(
                "Failed to fetch local HTTPS media image for %s from %s",
                self.entity_id,
                url,
            )

        return content, content_type

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
            if not self._device.supports_http_api:
                raise BrowseError("Media sources are not supported on this device")

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
            if self._device.supports_http_api:
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

    @media_player_exception_wrap
    async def async_join_players(self, group_members: list[str]) -> None:
        """Join group_members (entity_ids) to the group led by the current player."""
        follower_udns_to_join: list[str] = []
        for member_entity_id in group_members:
            if member_entity_id == self.entity_id:
                LOGGER.debug("Skipping joining self to group: %s", member_entity_id)
                continue

            follower_udn = self._wiim_data.entity_id_to_udn_map.get(member_entity_id)
            if follower_udn is None:
                LOGGER.warning(
                    "Unable to resolve group member entity_id %s to a UDN",
                    member_entity_id,
                )
                continue

            follower_udns_to_join.append(follower_udn)

        LOGGER.debug(
            "Player %s (UDN %s) joining follower UDNs: %s from entity_ids: %s",
            self.entity_id,
            self._device.udn,
            follower_udns_to_join,
            group_members,
        )
        await self._wiim_data.controller.async_join_group(
            self._device.udn, follower_udns_to_join
        )

    @media_player_exception_wrap
    async def async_unjoin_player(self) -> None:
        """Remove this player from any group it is currently in."""
        LOGGER.debug(
            "Player %s (UDN %s) attempting to unjoin from group",
            self.entity_id,
            self._device.udn,
        )
        await self._wiim_data.controller.async_ungroup_device(self._device.udn)
