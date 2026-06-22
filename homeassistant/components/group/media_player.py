"""Platform allowing several media players to be grouped into one media player."""

from contextlib import suppress
from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_PLAY_MEDIA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_SHUFFLE_SET,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import GroupEntity

KEY_ANNOUNCE = "announce"
KEY_CLEAR_PLAYLIST = "clear_playlist"
KEY_ENQUEUE = "enqueue"
KEY_ON_OFF = "on_off"
KEY_PAUSE_PLAY_STOP = "play"
KEY_PLAY_MEDIA = "play_media"
KEY_SHUFFLE = "shuffle"
KEY_SEEK = "seek"
KEY_TRACKS = "tracks"
KEY_VOLUME = "volume"

DEFAULT_NAME = "Media Group"

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain(MEDIA_PLAYER_DOMAIN),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MediaPlayer Group platform."""
    entities = {"entity_id": config[CONF_ENTITIES]}
    async_add_entities(
        [MediaPlayerGroup(config.get(CONF_UNIQUE_ID), config[CONF_NAME], entities)]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize MediaPlayer Group config entry."""
    target_config = dict(config_entry.options[CONF_ENTITIES])
    entity_ids = target_config.get("entity_id", [])
    if entity_ids:
        registry = er.async_get(hass)
        entities = er.async_validate_entity_ids(registry, entity_ids)
        target_config["entity_id"] = entities
    async_add_entities(
        [MediaPlayerGroup(config_entry.entry_id, config_entry.title, target_config)]
    )


@callback
def async_create_preview_media_player(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> MediaPlayerGroup:
    """Create a preview sensor."""
    return MediaPlayerGroup(
        None,
        name,
        validated_config[CONF_ENTITIES],
    )


class MediaPlayerGroup(GroupEntity, MediaPlayerEntity):
    """Representation of a Media Group."""

    _attr_available: bool = False

    def __init__(
        self, unique_id: str | None, name: str, target_config: dict[str, Any]
    ) -> None:
        """Initialize a Media Group entity."""
        super().__init__()
        self._target_config = target_config
        self._domains = [MEDIA_PLAYER_DOMAIN]
        self._name = name
        self._attr_unique_id = unique_id
        self._features: dict[str, set[str]] = {
            KEY_ANNOUNCE: set(),
            KEY_CLEAR_PLAYLIST: set(),
            KEY_ENQUEUE: set(),
            KEY_ON_OFF: set(),
            KEY_PAUSE_PLAY_STOP: set(),
            KEY_PLAY_MEDIA: set(),
            KEY_SHUFFLE: set(),
            KEY_SEEK: set(),
            KEY_TRACKS: set(),
            KEY_VOLUME: set(),
        }

    @callback
    def async_update_supported_features(
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
        if new_features & MediaPlayerEntityFeature.CLEAR_PLAYLIST:
            self._features[KEY_CLEAR_PLAYLIST].add(entity_id)
        else:
            self._features[KEY_CLEAR_PLAYLIST].discard(entity_id)
        if new_features & (
            MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
        ):
            self._features[KEY_TRACKS].add(entity_id)
        else:
            self._features[KEY_TRACKS].discard(entity_id)
        if new_features & (
            MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.STOP
        ):
            self._features[KEY_PAUSE_PLAY_STOP].add(entity_id)
        else:
            self._features[KEY_PAUSE_PLAY_STOP].discard(entity_id)
        if new_features & MediaPlayerEntityFeature.PLAY_MEDIA:
            self._features[KEY_PLAY_MEDIA].add(entity_id)
        else:
            self._features[KEY_PLAY_MEDIA].discard(entity_id)
        if new_features & MediaPlayerEntityFeature.SEEK:
            self._features[KEY_SEEK].add(entity_id)
        else:
            self._features[KEY_SEEK].discard(entity_id)
        if new_features & MediaPlayerEntityFeature.SHUFFLE_SET:
            self._features[KEY_SHUFFLE].add(entity_id)
        else:
            self._features[KEY_SHUFFLE].discard(entity_id)
        if new_features & (
            MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
        ):
            self._features[KEY_ON_OFF].add(entity_id)
        else:
            self._features[KEY_ON_OFF].discard(entity_id)
        if new_features & (
            MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
        ):
            self._features[KEY_VOLUME].add(entity_id)
        else:
            self._features[KEY_VOLUME].discard(entity_id)
        if new_features & MediaPlayerEntityFeature.MEDIA_ANNOUNCE:
            self._features[KEY_ANNOUNCE].add(entity_id)
        else:
            self._features[KEY_ANNOUNCE].discard(entity_id)
        if new_features & MediaPlayerEntityFeature.MEDIA_ENQUEUE:
            self._features[KEY_ENQUEUE].add(entity_id)
        else:
            self._features[KEY_ENQUEUE].discard(entity_id)

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        data = {ATTR_ENTITY_ID: self._features[KEY_CLEAR_PLAYLIST]}
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_CLEAR_PLAYLIST,
            data,
            context=self._context,
        )

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        data = {ATTR_ENTITY_ID: self._features[KEY_TRACKS]}
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            data,
            context=self._context,
        )

    async def async_media_pause(self) -> None:
        """Send pause command."""
        data = {ATTR_ENTITY_ID: self._features[KEY_PAUSE_PLAY_STOP]}
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PAUSE,
            data,
            context=self._context,
        )

    async def async_media_play(self) -> None:
        """Send play command."""
        data = {ATTR_ENTITY_ID: self._features[KEY_PAUSE_PLAY_STOP]}
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PLAY,
            data,
            context=self._context,
        )

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        data = {ATTR_ENTITY_ID: self._features[KEY_TRACKS]}
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            data,
            context=self._context,
        )

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        data = {
            ATTR_ENTITY_ID: self._features[KEY_SEEK],
            ATTR_MEDIA_SEEK_POSITION: position,
        }
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_SEEK,
            data,
            context=self._context,
        )

    async def async_media_stop(self) -> None:
        """Send stop command."""
        data = {ATTR_ENTITY_ID: self._features[KEY_PAUSE_PLAY_STOP]}
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
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
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_MUTE,
            data,
            context=self._context,
        )

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        data = {
            ATTR_ENTITY_ID: self._features[KEY_PLAY_MEDIA],
            ATTR_MEDIA_CONTENT_ID: media_id,
            ATTR_MEDIA_CONTENT_TYPE: media_type,
        }
        if kwargs:
            data.update(kwargs)
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            data,
            context=self._context,
        )

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        data = {
            ATTR_ENTITY_ID: self._features[KEY_SHUFFLE],
            ATTR_MEDIA_SHUFFLE: shuffle,
        }
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SHUFFLE_SET,
            data,
            context=self._context,
        )

    async def async_turn_on(self) -> None:
        """Forward the turn_on command to all media in the media group."""
        data = {ATTR_ENTITY_ID: self._features[KEY_ON_OFF]}
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
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
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_SET,
            data,
            context=self._context,
        )

    async def async_turn_off(self) -> None:
        """Forward the turn_off command to all media in the media group."""
        data = {ATTR_ENTITY_ID: self._features[KEY_ON_OFF]}
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_TURN_OFF,
            data,
            context=self._context,
        )

    async def async_volume_up(self) -> None:
        """Turn volume up for media player(s)."""
        for entity in self._features[KEY_VOLUME]:
            volume_level = self.hass.states.get(entity).attributes["volume_level"]  # type: ignore[union-attr]
            if volume_level < 1:
                await self.async_set_volume_level(min(1, volume_level + 0.1))

    async def async_volume_down(self) -> None:
        """Turn volume down for media player(s)."""
        for entity in self._features[KEY_VOLUME]:
            volume_level = self.hass.states.get(entity).attributes["volume_level"]  # type: ignore[union-attr]
            if volume_level > 0:
                await self.async_set_volume_level(max(0, volume_level - 0.1))

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the media group state."""
        states = [
            state.state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]

        # Set group as unavailable if all members are unavailable or missing
        self._attr_available = any(state != STATE_UNAVAILABLE for state in states)

        valid_state = any(
            state not in (STATE_UNKNOWN, STATE_UNAVAILABLE) for state in states
        )
        if not valid_state:
            # Set as unknown if all members are unknown or unavailable
            self._attr_state = None
        else:
            off_values = {MediaPlayerState.OFF, STATE_UNAVAILABLE, STATE_UNKNOWN}
            if states.count(single_state := states[0]) == len(states):
                self._attr_state = None
                with suppress(ValueError):
                    self._attr_state = MediaPlayerState(single_state)
            elif any(state for state in states if state not in off_values):
                self._attr_state = MediaPlayerState.ON
            else:
                self._attr_state = MediaPlayerState.OFF

        supported_features = MediaPlayerEntityFeature(0)
        if self._features[KEY_CLEAR_PLAYLIST]:
            supported_features |= MediaPlayerEntityFeature.CLEAR_PLAYLIST
        if self._features[KEY_TRACKS]:
            supported_features |= (
                MediaPlayerEntityFeature.NEXT_TRACK
                | MediaPlayerEntityFeature.PREVIOUS_TRACK
            )
        if self._features[KEY_PAUSE_PLAY_STOP]:
            supported_features |= (
                MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.STOP
            )
        if self._features[KEY_PLAY_MEDIA]:
            supported_features |= MediaPlayerEntityFeature.PLAY_MEDIA
        if self._features[KEY_SEEK]:
            supported_features |= MediaPlayerEntityFeature.SEEK
        if self._features[KEY_SHUFFLE]:
            supported_features |= MediaPlayerEntityFeature.SHUFFLE_SET
        if self._features[KEY_ON_OFF]:
            supported_features |= (
                MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
            )
        if self._features[KEY_VOLUME]:
            supported_features |= (
                MediaPlayerEntityFeature.VOLUME_MUTE
                | MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
            )
        if self._features[KEY_ANNOUNCE]:
            supported_features |= MediaPlayerEntityFeature.MEDIA_ANNOUNCE
        if self._features[KEY_ENQUEUE]:
            supported_features |= MediaPlayerEntityFeature.MEDIA_ENQUEUE

        self._attr_supported_features = supported_features
