"""MediaPlayer platform for SlimProto Player integration."""
from __future__ import annotations

import asyncio
from typing import Any

from aioslimproto.client import PlayerState, SlimClient
from aioslimproto.const import EventType, SlimEvent
from aioslimproto.server import SlimServer

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import DEFAULT_NAME, DOMAIN, PLAYER_EVENT

STATE_MAPPING = {
    PlayerState.IDLE: MediaPlayerState.IDLE,
    PlayerState.PLAYING: MediaPlayerState.PLAYING,
    PlayerState.PAUSED: MediaPlayerState.PAUSED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SlimProto MediaPlayer(s) from Config Entry."""
    slimserver: SlimServer = hass.data[DOMAIN]
    added_ids = set()

    async def async_add_player(player: SlimClient) -> None:
        """Add MediaPlayerEntity from SlimClient."""
        # we delay adding the player a small bit because the player name may be received
        # just a bit after connect. This way we can create a device reg entry with the correct name
        # the name will either be available within a few milliseconds after connect or not at all
        # (its an optional data packet)
        for _ in range(10):
            if player.player_id not in player.name:
                break
            await asyncio.sleep(0.1)
        async_add_entities([SlimProtoPlayer(slimserver, player)])

    async def on_slim_event(event: SlimEvent) -> None:
        """Handle player added/connected event."""
        if event.player_id in added_ids:
            return
        added_ids.add(event.player_id)
        player = slimserver.get_player(event.player_id)
        await async_add_player(player)

    # register listener for new players
    config_entry.async_on_unload(
        slimserver.subscribe(on_slim_event, EventType.PLAYER_CONNECTED)
    )

    # add all current items in controller
    await asyncio.gather(*(async_add_player(player) for player in slimserver.players))


class SlimProtoPlayer(MediaPlayerEntity):
    """Representation of MediaPlayerEntity from SlimProto Player."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    def __init__(self, slimserver: SlimServer, player: SlimClient) -> None:
        """Initialize MediaPlayer entity."""
        self.slimserver = slimserver
        self.player = player
        self._attr_unique_id = player.player_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.player.player_id)},
            manufacturer=DEFAULT_NAME,
            model=self.player.device_model or self.player.device_type,
            name=self.player.name,
            hw_version=self.player.firmware,
        )
        # PiCore + SqueezeESP32 player has web interface
        if "-pCP" in self.player.firmware or self.player.device_model == "SqueezeESP32":
            self._attr_device_info[
                "configuration_url"
            ] = f"http://{self.player.device_address}"
        self.update_attributes()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.update_attributes()
        self.async_on_remove(
            self.slimserver.subscribe(
                self._on_slim_event,
                (
                    EventType.PLAYER_UPDATED,
                    EventType.PLAYER_CONNECTED,
                    EventType.PLAYER_DISCONNECTED,
                    EventType.PLAYER_NAME_RECEIVED,
                    EventType.PLAYER_CLI_EVENT,
                ),
                player_filter=self.player.player_id,
            )
        )

    @property
    def available(self) -> bool:
        """Return availability of entity."""
        return self.player.connected

    @property
    def state(self) -> MediaPlayerState:
        """Return current state."""
        if not self.player.powered:
            return MediaPlayerState.OFF
        return STATE_MAPPING[self.player.state]

    @callback
    def update_attributes(self) -> None:
        """Handle player updates."""
        self._attr_volume_level = self.player.volume_level / 100
        self._attr_media_position = self.player.elapsed_seconds
        self._attr_media_position_updated_at = utcnow()
        self._attr_media_content_id = self.player.current_url
        self._attr_media_content_type = "music"

    async def async_media_play(self) -> None:
        """Send play command to device."""
        await self.player.play()

    async def async_media_pause(self) -> None:
        """Send pause command to device."""
        await self.player.pause()

    async def async_media_stop(self) -> None:
        """Send stop command to device."""
        await self.player.stop()

    async def async_set_volume_level(self, volume: float) -> None:
        """Send new volume_level to device."""
        volume = round(volume * 100)
        await self.player.volume_set(volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.player.mute(mute)

    async def async_turn_on(self) -> None:
        """Turn on device."""
        await self.player.power(True)

    async def async_turn_off(self) -> None:
        """Turn off device."""
        await self.player.power(False)

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the play_media command to the media player."""
        to_send_media_type: str | None = media_type
        # Handle media_source
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = sourced_media.url
            to_send_media_type = sourced_media.mime_type

        if to_send_media_type and not to_send_media_type.startswith("audio/"):
            to_send_media_type = None
        media_id = async_process_play_media_url(self.hass, media_id)

        await self.player.play_url(media_id, mime_type=to_send_media_type)

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    async def _on_slim_event(self, event: SlimEvent) -> None:
        """Call when we receive an event from SlimProto."""
        if event.type == EventType.PLAYER_CONNECTED:
            # player reconnected, update our player object
            self.player = self.slimserver.get_player(event.player_id)
        if event.type == EventType.PLAYER_CLI_EVENT:
            # rpc event from player such as a button press,
            # forward on the eventbus for others to handle
            dev_id = self.registry_entry.device_id if self.registry_entry else None
            evt_data = {
                **event.data,
                "entity_id": self.entity_id,
                "device_id": dev_id,
            }
            self.hass.bus.async_fire(PLAYER_EVENT, evt_data)
            return
        self.update_attributes()
        self.async_write_ha_state()
