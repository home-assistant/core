"""Media player platform for AirLino."""

from collections.abc import Awaitable, Callable
from datetime import datetime
import logging
from typing import Any, override
from urllib.parse import urlsplit

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.components.media_source import is_media_source_id
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirlinoConfigEntry, AirlinoRuntimeData
from .api import AirlinoApiConnectionError, AirlinoApiError
from .const import (
    DOMAIN,
    PLAYER_STATE_PAUSED,
    PLAYER_STATE_PLAYING,
    PLAYER_STATE_STOPPED,
    RECEIVER_STATE_NOT_PLAYING,
    RECEIVER_STATE_PLAYING,
    SENDER_STATE_PLAYING,
    VOLUME_MAX,
)
from .coordinator import AirlinoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

STATE_MAP = {
    PLAYER_STATE_STOPPED: MediaPlayerState.IDLE,
    PLAYER_STATE_PLAYING: MediaPlayerState.PLAYING,
    PLAYER_STATE_PAUSED: MediaPlayerState.PAUSED,
}

SOURCE_TO_MEDIA_TYPE = {
    "radio": MediaType.CHANNEL,
    "tidal": MediaType.MUSIC,
    "qobuz": MediaType.MUSIC,
    "other": MediaType.MUSIC,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirlinoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AirLino media player from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([AirlinoMediaPlayer(coordinator, entry)])


class AirlinoMediaPlayer(
    CoordinatorEntity[AirlinoDataUpdateCoordinator], MediaPlayerEntity
):
    """Representation of an AirLino media player."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.GROUPING
    )

    @override
    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the supported features.

        A device that is part of a multiroom group as a slave (Songcast
        receiver) follows the master's stream; only the local volume stays
        controllable, so all other features are disabled.
        """
        if self.is_multiroom_receiver:
            return (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
                | MediaPlayerEntityFeature.GROUPING
            )
        return self._attr_supported_features

    @property
    def is_multiroom_receiver(self) -> bool:
        """Return True if this device is a slave in a multiroom group."""
        if self._sender_uuid(self.coordinator):
            return False
        return bool(self._receiver_sender_uuid(self.coordinator))

    def __init__(
        self,
        coordinator: AirlinoDataUpdateCoordinator,
        entry: AirlinoConfigEntry,
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        assert entry.unique_id is not None
        self._attr_unique_id = entry.unique_id
        self._device_name = entry.title
        self._attr_name = None

    @override
    @property
    def available(self) -> bool:
        """Return if the device is available.

        The device cannot be turned on remotely, so when it is unreachable (e.g. in standby) it is shown as unavailable.
        """
        return self.coordinator.data.get("online", False)

    @override
    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info for the device registry."""
        assert self._attr_unique_id is not None
        device = self.coordinator.data.get("device") or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=device.get("devicename") or self._device_name,
            manufacturer="Lintech GmbH",
            model=device.get("model"),
            sw_version=device.get("firmware"),
        )

    def _entity_id_for_entry(self, entry: AirlinoConfigEntry) -> str | None:
        """Return the media player entity id of an AirLino config entry."""
        assert entry.unique_id is not None
        registry = er.async_get(self.hass)
        return registry.async_get_entity_id("media_player", DOMAIN, entry.unique_id)

    def _all_runtimes(self) -> list[tuple[AirlinoConfigEntry, AirlinoRuntimeData]]:
        """Return the config entries and runtime data of all AirLino devices."""
        return [
            (entry, entry.runtime_data)
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if isinstance(getattr(entry, "runtime_data", None), AirlinoRuntimeData)
        ]

    def _sender_uuid(self, coordinator: AirlinoDataUpdateCoordinator) -> str | None:
        """Return the sender UUID of a device, if it is broadcasting."""
        data = coordinator.data or {}
        sender = data.get("sender") or {}
        return sender["uuid"] if sender.get("enabled") else None

    def _receiver_sender_uuid(
        self, coordinator: AirlinoDataUpdateCoordinator
    ) -> str | None:
        """Return the sender UUID a device is linked to, if any."""
        data = coordinator.data or {}
        receiver = data.get("receiver") or {}
        return receiver.get("sender")

    @override
    @property
    def group_members(self) -> list[str] | None:
        """Return the members of the multiroom group this device belongs to."""
        sender_uuid = self._sender_uuid(self.coordinator) or self._receiver_sender_uuid(
            self.coordinator
        )
        if not sender_uuid:
            return None
        members: set[str] = set()
        for entry, runtime in self._all_runtimes():
            is_master = self._sender_uuid(runtime.coordinator) == sender_uuid
            is_member = self._receiver_sender_uuid(runtime.coordinator) == sender_uuid
            if not (is_master or is_member):
                continue
            entity_id = self._entity_id_for_entry(entry)
            if entity_id:
                members.add(entity_id)
        if not members:
            return None
        return sorted(members)

    async def _async_find_runtime_by_entity_id(
        self, entity_id: str
    ) -> AirlinoRuntimeData | None:
        """Return the runtime data of the device behind a media player entity id."""
        for entry, runtime in self._all_runtimes():
            if self._entity_id_for_entry(entry) == entity_id:
                return runtime
        return None

    @override
    async def async_join_players(self, group_members: list[str]) -> None:
        """Add devices to the multiroom group (Songcast sender/receiver)."""
        self._ensure_not_multiroom_receiver()
        # Grouping is purely sender enable + receiver link: a linked receiver
        # starts playing the sender's stream on its own once connected.
        sender_status: dict[str, Any] = await self._async_call(
            self.coordinator.api.async_get_sender_status
        )
        uuid: str | None = (sender_status or {}).get("uuid")
        if not uuid:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="sender_uuid_missing",
            )

        if not (sender_status or {}).get("enabled"):
            await self._async_call(self.coordinator.api.async_enable_sender)
        for entity_id in group_members:
            runtime = await self._async_find_runtime_by_entity_id(entity_id)
            if runtime is None:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="entity_not_found",
                    translation_placeholders={"entity_id": entity_id},
                )
            if not (runtime.coordinator.data or {}).get("online"):
                # The device is unreachable (e.g. powered off): abort so the
                # user gets a visible error in the UI instead of a group that
                # silently misses one member.
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="device_unavailable",
                    translation_placeholders={"entity_id": entity_id},
                )
            receiver_state: dict[str, Any] = await self._async_call(
                runtime.api.async_get_receiver_state
            )
            if (receiver_state or {}).get("sender") != uuid:
                # Not linked (or linked to another sender): link to ours.
                if (receiver_state or {}).get("sender"):
                    await self._async_call(runtime.api.async_receiver_unlink)
                await self._async_call(runtime.api.async_receiver_link, uuid)
            await runtime.coordinator.async_request_refresh()
        await self.coordinator.async_request_refresh()

    @override
    async def async_unjoin_player(self) -> None:
        """Remove this device from the multiroom group."""
        uuid = self._sender_uuid(self.coordinator)
        if uuid:
            # This device is the sender: unlink all group members and stop
            # broadcasting, returning it to standalone mode.
            for _, runtime in self._all_runtimes():
                if runtime.coordinator is self.coordinator:
                    continue
                if self._receiver_sender_uuid(runtime.coordinator) == uuid:
                    await self._async_call(runtime.api.async_receiver_unlink)
                    await runtime.coordinator.async_request_refresh()
            await self._async_call(self.coordinator.api.async_disable_sender)
        else:
            await self._async_call(self.coordinator.api.async_receiver_unlink)
            # If the last slave left, release the master back to standalone
            # mode so that no one-device group stays behind.
            master_uuid = self._receiver_sender_uuid(self.coordinator)
            if master_uuid:
                await self._async_dissolve_group_if_empty(master_uuid)
        await self.coordinator.async_request_refresh()

    async def _async_dissolve_group_if_empty(self, master_uuid: str) -> None:
        """Disable the sender if no receiver is linked to it anymore."""
        for _, runtime in self._all_runtimes():
            if self._sender_uuid(runtime.coordinator) != master_uuid:
                continue
            # Found the master: check whether any other device is still
            # linked to it (this device just left the group).
            still_linked = any(
                self._receiver_sender_uuid(other_runtime.coordinator) == master_uuid
                for _, other_runtime in self._all_runtimes()
                if other_runtime.coordinator is not runtime.coordinator
                and other_runtime.coordinator is not self.coordinator
            )
            if not still_linked:
                await self._async_call(runtime.api.async_disable_sender)
                await runtime.coordinator.async_request_refresh()
            break

    @override
    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current playback state."""
        player = self.coordinator.data.get("player", {})
        sender = self.coordinator.data.get("sender") or {}
        receiver = self.coordinator.data.get("receiver") or {}
        receiver_state = receiver.get("state")
        if receiver_state == RECEIVER_STATE_PLAYING:
            return MediaPlayerState.PLAYING
        if receiver_state == RECEIVER_STATE_NOT_PLAYING:
            return MediaPlayerState.PAUSED
        if sender.get("enabled"):
            if sender.get("state") == SENDER_STATE_PLAYING:
                return MediaPlayerState.PLAYING
            return MediaPlayerState.IDLE
        return STATE_MAP.get(player.get("state"))

    @override
    @property
    def volume_level(self) -> float | None:
        """Return the volume level (0.0 - 1.0)."""
        volume = self.coordinator.data.get("volume")
        if volume is None:
            return None
        return volume / VOLUME_MAX

    @override
    @property
    def media_content_type(self) -> MediaType | None:
        """Content type of current playing media."""
        status = self.coordinator.data.get("player", {}).get("status") or {}
        source = status.get("source")
        if not isinstance(source, str):
            return None
        return SOURCE_TO_MEDIA_TYPE.get(source)

    @override
    @property
    def media_title(self) -> str | None:
        """Return the title of the current media."""
        status = self.coordinator.data.get("player", {}).get("status") or {}
        station = status.get("station") or {}
        meta = station.get("meta") or {}
        if meta.get("now_playing"):
            return meta["now_playing"]
        if station.get("name"):
            return station["name"]
        track = status.get("track") or {}
        track_meta = track.get("meta") or {}
        if track_meta.get("title"):
            title = track_meta["title"]
            if track_meta.get("artist"):
                title = f"{track_meta['artist']} - {title}"
            return title
        return None

    @override
    @property
    def media_image_url(self) -> str | None:
        """Return the image URL of the current media."""
        status = self.coordinator.data.get("player", {}).get("status") or {}
        station = status.get("station") or {}
        track = status.get("track") or {}
        return station.get("image") or track.get("image")

    @override
    @property
    def media_duration(self) -> int | None:
        """Return the duration of the current track in seconds."""
        status = self.coordinator.data.get("player", {}).get("status") or {}
        track = status.get("track") or {}
        return track.get("totaltime")

    @override
    @property
    def media_position(self) -> int | None:
        """Return the elapsed playback time in seconds."""
        status = self.coordinator.data.get("player", {}).get("status") or {}
        return status.get("elapsedtime")

    @override
    @property
    def media_position_updated_at(self) -> datetime | None:
        """When the media position was last updated."""
        updated_at = self.coordinator.data.get("updated_at")
        if isinstance(updated_at, datetime):
            return updated_at
        return None

    async def _async_call(
        self, action: Callable[..., Awaitable[Any]], *args: Any
    ) -> Any:
        """Call an API action, raise on failure and return the response."""
        try:
            return await action(*args)
        except (AirlinoApiConnectionError, AirlinoApiError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"err": str(err)},
            ) from err

    def _ensure_not_multiroom_receiver(self) -> None:
        """Reject commands that a multiroom slave cannot execute."""
        if self.is_multiroom_receiver:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="multiroom_receiver_control",
            )

    @override
    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse Home Assistant media sources (no own media sources)."""
        # media_content_id is sufficient for routing to the media source
        # integration; the content type is ignored.
        del media_content_type
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    @override
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media (URL or media source)."""
        self._ensure_not_multiroom_receiver()
        if is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = async_process_play_media_url(self.hass, play_item.url)
        elif media_type not in (MediaType.URL, "url"):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="media_type_unsupported",
                translation_placeholders={"media_type": media_type},
            )

        if urlsplit(media_id).scheme == "https":
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="https_unsupported",
            )

        _LOGGER.debug("Playing media on AirLino: %s", media_id)
        previous_error = self.coordinator.data.get("error")
        await self._async_call(self.coordinator.api.async_play_station, media_id)
        await self.coordinator.async_request_refresh()
        # The device accepts the play command even if it cannot decode the
        # stream; the failure is only reported in the player status.
        error = self.coordinator.data.get("error")
        if error and error != previous_error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="play_failed",
                translation_placeholders={"error": error},
            )

    @override
    async def async_media_play(self) -> None:
        """Start playback."""
        self._ensure_not_multiroom_receiver()
        if self.state == MediaPlayerState.PLAYING:
            return
        await self._async_call(self.coordinator.api.async_play)

    @override
    async def async_media_pause(self) -> None:
        """Pause playback when it is currently playing."""
        self._ensure_not_multiroom_receiver()
        if self.state != MediaPlayerState.PLAYING:
            return
        await self._async_call(self.coordinator.api.async_playpause)

    @override
    async def async_media_play_pause(self) -> None:
        """Toggle between play and pause."""
        self._ensure_not_multiroom_receiver()
        await self._async_call(self.coordinator.api.async_playpause)

    @override
    async def async_media_stop(self) -> None:
        """Stop playback."""
        self._ensure_not_multiroom_receiver()
        await self._async_call(self.coordinator.api.async_stop)
        await self.coordinator.async_request_refresh()

    @override
    async def async_media_next_track(self) -> None:
        """Play next track."""
        self._ensure_not_multiroom_receiver()
        await self._async_call(self.coordinator.api.async_next)
        await self.coordinator.async_request_refresh()

    @override
    async def async_media_previous_track(self) -> None:
        """Play previous track."""
        self._ensure_not_multiroom_receiver()
        await self._async_call(self.coordinator.api.async_previous)
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level (0.0 - 1.0)."""
        await self._async_call(
            self.coordinator.api.async_set_master_volume,
            round(volume * VOLUME_MAX),
        )
        await self.coordinator.async_request_refresh()

    @override
    async def async_volume_up(self) -> None:
        """Increase the volume."""
        await self._async_call(self.coordinator.api.async_volume_up)

    @override
    async def async_volume_down(self) -> None:
        """Decrease the volume."""
        await self._async_call(self.coordinator.api.async_volume_down)
