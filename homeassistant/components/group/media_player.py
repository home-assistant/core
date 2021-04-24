"""This platform allows several media players to be grouped into one media player."""
from __future__ import annotations

from typing import Any, Callable

import voluptuous as vol

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN,
    PLATFORM_SCHEMA,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_PLAY_MEDIA,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
    MediaPlayerEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITIES,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import State
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    EventType,
    HomeAssistantType,
)

KEY_CLEAR_PLAYLIST = "clear_playlist"
KEY_ON_OFF = "on_off"
KEY_PAUSE_PLAY_STOP = "play"
KEY_PLAY_MEDIA = "play_media"
KEY_SHUFFLE = "shuffle"
KEY_SEEK = "seek"
KEY_TRACKS = "tracks"
KEY_VOLUME = "volume"

DEFAULT_NAME = "Media Group"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_ENTITIES): cv.entities_domain(DOMAIN),
    }
)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Media Group platform."""
    async_add_entities([MediaGroup(config[CONF_NAME], config[CONF_ENTITIES])])


class MediaGroup(MediaPlayerEntity):
    """Representation of a Media Group."""

    def __init__(self, name: str, entities: list[str]) -> None:
        """Initialize a Media Group entity."""
        self._name = name
        self._state: str | None = None
        self._supported_features: int = 0

        self._entities = entities
        self._features: dict[str, set[str]] = {
            KEY_CLEAR_PLAYLIST: set(),
            KEY_ON_OFF: set(),
            KEY_PAUSE_PLAY_STOP: set(),
            KEY_PLAY_MEDIA: set(),
            KEY_SHUFFLE: set(),
            KEY_SEEK: set(),
            KEY_TRACKS: set(),
            KEY_VOLUME: set(),
        }

    async def _on_state_change(self, event: EventType) -> None:
        self.async_set_context(event.context)
        await self.async_update_supported_features(
            event.data.get("entity_id"), event.data.get("new_state")  # type: ignore
        )
        await self.async_update_state()

    async def async_update_supported_features(
        self,
        entity_id: str,
        new_state: State | None,
    ) -> None:
        """Update dictionaries with supported features."""
        if not new_state:
            for players in self._features.values():
                players.discard(entity_id)
            return

        new_features = new_state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if new_features & SUPPORT_CLEAR_PLAYLIST:
            self._features[KEY_CLEAR_PLAYLIST].add(entity_id)
        else:
            self._features[KEY_CLEAR_PLAYLIST].discard(entity_id)
        if new_features & (SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK):
            self._features[KEY_TRACKS].add(entity_id)
        else:
            self._features[KEY_TRACKS].discard(entity_id)
        if new_features & (SUPPORT_PAUSE | SUPPORT_PLAY | SUPPORT_STOP):
            self._features[KEY_PAUSE_PLAY_STOP].add(entity_id)
        else:
            self._features[KEY_PAUSE_PLAY_STOP].discard(entity_id)
        if new_features & SUPPORT_PLAY_MEDIA:
            self._features[KEY_PLAY_MEDIA].add(entity_id)
        else:
            self._features[KEY_PLAY_MEDIA].discard(entity_id)
        if new_features & SUPPORT_SEEK:
            self._features[KEY_SEEK].add(entity_id)
        else:
            self._features[KEY_SEEK].discard(entity_id)
        if new_features & SUPPORT_SHUFFLE_SET:
            self._features[KEY_SHUFFLE].add(entity_id)
        else:
            self._features[KEY_SHUFFLE].discard(entity_id)
        if new_features & (SUPPORT_TURN_ON | SUPPORT_TURN_OFF):
            self._features[KEY_ON_OFF].add(entity_id)
        else:
            self._features[KEY_ON_OFF].discard(entity_id)
        if new_features & (
            SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP
        ):
            self._features[KEY_VOLUME].add(entity_id)
        else:
            self._features[KEY_VOLUME].discard(entity_id)

    async def async_added_to_hass(self) -> None:
        """Register listeners."""
        for entity_id in self._entities:
            new_state = self.hass.states.get(entity_id)
            await self.async_update_supported_features(entity_id, new_state)
        async_track_state_change_event(self.hass, self._entities, self._on_state_change)
        await self.async_update_state()

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state of the media group."""
        return self._state or STATE_OFF

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def should_poll(self) -> bool:
        """No polling needed for a media group."""
        return False

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes for the media group."""
        return {ATTR_ENTITY_ID: self._entities}

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        data = {ATTR_ENTITY_ID: self._features[KEY_TRACKS]}
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            data,
            context=self._context,
        )

    async def async_media_pause(self) -> None:
        """Send pause command."""
        data = {ATTR_ENTITY_ID: self._features[KEY_PAUSE_PLAY_STOP]}
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_MEDIA_PAUSE,
            data,
            context=self._context,
        )

    async def async_media_play(self) -> None:
        """Send play command."""
        data = {ATTR_ENTITY_ID: self._features[KEY_PAUSE_PLAY_STOP]}
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_MEDIA_PLAY,
            data,
            context=self._context,
        )

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        data = {ATTR_ENTITY_ID: self._features[KEY_TRACKS]}
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            data,
            context=self._context,
        )

    async def async_media_seek(self, position: int) -> None:
        """Send seek command."""
        data = {
            ATTR_ENTITY_ID: self._features[KEY_SEEK],
            ATTR_MEDIA_SEEK_POSITION: position,
        }
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_MEDIA_SEEK,
            data,
            context=self._context,
        )

    async def async_media_stop(self) -> None:
        """Send stop command."""
        data = {ATTR_ENTITY_ID: self._features[KEY_PAUSE_PLAY_STOP]}
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_MEDIA_STOP,
            data,
            context=self._context,
        )

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        data = {
            ATTR_ENTITY_ID: self._features[KEY_VOLUME],
            ATTR_MEDIA_VOLUME_MUTED: mute,
        }
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_VOLUME_MUTE,
            data,
            context=self._context,
        )

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        data = {
            ATTR_ENTITY_ID: self._features[KEY_PLAY_MEDIA],
            ATTR_MEDIA_CONTENT_ID: media_id,
            ATTR_MEDIA_CONTENT_TYPE: media_type,
        }
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_MEDIA,
            data,
            context=self._context,
        )

    async def async_turn_on(self) -> None:
        """Forward the turn_on command to all media in the media group."""
        data = {ATTR_ENTITY_ID: self._features[KEY_ON_OFF]}
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            data,
            context=self._context,
        )

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level(s)."""
        data = {
            ATTR_ENTITY_ID: self._features[KEY_VOLUME],
            ATTR_MEDIA_VOLUME_LEVEL: volume,
        }
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_VOLUME_SET,
            data,
            context=self._context,
        )

    async def async_turn_off(self) -> None:
        """Forward the turn_off command to all media in the media group."""
        data = {ATTR_ENTITY_ID: self._features[KEY_ON_OFF]}
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_OFF,
            data,
            context=self._context,
        )

    async def async_volume_up(self) -> None:
        """Turn volume up for media player(s)."""
        for entity in self._features[KEY_VOLUME]:
            volume_level = self.hass.states.get(entity).attributes["volume_level"]  # type: ignore
            if volume_level < 1:
                await self.async_set_volume_level(min(1, volume_level + 0.1))

    async def async_volume_down(self) -> None:
        """Turn volume down for media player(s)."""
        for entity in self._features[KEY_VOLUME]:
            volume_level = self.hass.states.get(entity).attributes["volume_level"]  # type: ignore
            if volume_level > 0:
                await self.async_set_volume_level(max(0, volume_level - 0.1))

    async def async_update_state(self) -> None:
        """Query all members and determine the media group state."""
        states = [self.hass.states.get(entity) for entity in self._entities]
        states_values = [state.state for state in states if state is not None]
        off_values = STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN

        if states_values:
            if states_values.count(states_values[0]) == len(states_values):
                self._state = states_values[0]
            elif any(state for state in states_values if state not in off_values):
                self._state = STATE_ON
            else:
                self._state = STATE_OFF
        else:
            self._state = STATE_UNKNOWN

        supported_features = 0
        supported_features |= (
            SUPPORT_CLEAR_PLAYLIST if self._features[KEY_CLEAR_PLAYLIST] else 0
        )
        supported_features |= (
            SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK
            if self._features[KEY_TRACKS]
            else 0
        )
        supported_features |= (
            SUPPORT_PAUSE | SUPPORT_PLAY | SUPPORT_STOP
            if self._features[KEY_PAUSE_PLAY_STOP]
            else 0
        )
        supported_features |= (
            SUPPORT_PLAY_MEDIA if self._features[KEY_PLAY_MEDIA] else 0
        )
        supported_features |= SUPPORT_SEEK if self._features[KEY_SEEK] else 0
        supported_features |= SUPPORT_SHUFFLE_SET if self._features[KEY_SHUFFLE] else 0
        supported_features |= (
            SUPPORT_TURN_ON | SUPPORT_TURN_OFF if self._features[KEY_ON_OFF] else 0
        )
        supported_features |= (
            SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP
            if self._features[KEY_VOLUME]
            else 0
        )

        self._supported_features = supported_features
        self.async_write_ha_state()
