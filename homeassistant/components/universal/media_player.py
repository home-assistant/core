"""Combination of multiple media players for a universal controller."""
from __future__ import annotations

from copy import copy
from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import (
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_EPISODE,
    ATTR_MEDIA_PLAYLIST,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEASON,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SERIES_TITLE,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    PLATFORM_SCHEMA,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.components.media_player.browse_media import BrowseMedia
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    ATTR_SUPPORTED_FEATURES,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_STATE,
    CONF_STATE_TEMPLATE,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_START,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    TrackTemplate,
    async_track_state_change_event,
    async_track_template_result,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.service import async_call_from_config
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

ATTR_ACTIVE_CHILD = "active_child"

CONF_ATTRS = "attributes"
CONF_CHILDREN = "children"
CONF_COMMANDS = "commands"
CONF_BROWSE_MEDIA_ENTITY = "browse_media_entity"

STATES_ORDER = [
    STATE_UNKNOWN,
    STATE_UNAVAILABLE,
    MediaPlayerState.OFF,
    MediaPlayerState.IDLE,
    MediaPlayerState.STANDBY,
    MediaPlayerState.ON,
    MediaPlayerState.PAUSED,
    MediaPlayerState.BUFFERING,
    MediaPlayerState.PLAYING,
]
STATES_ORDER_LOOKUP = {state: idx for idx, state in enumerate(STATES_ORDER)}
STATES_ORDER_IDLE = STATES_ORDER_LOOKUP[MediaPlayerState.IDLE]

ATTRS_SCHEMA = cv.schema_with_slug_keys(cv.string)
CMD_SCHEMA = cv.schema_with_slug_keys(cv.SERVICE_SCHEMA)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_CHILDREN, default=[]): cv.entity_ids,
        vol.Optional(CONF_COMMANDS, default={}): CMD_SCHEMA,
        vol.Optional(CONF_ATTRS, default={}): vol.Or(
            cv.ensure_list(ATTRS_SCHEMA), ATTRS_SCHEMA
        ),
        vol.Optional(CONF_BROWSE_MEDIA_ENTITY): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_STATE_TEMPLATE): cv.template,
    },
    extra=vol.REMOVE_EXTRA,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the universal media players."""
    await async_setup_reload_service(hass, "universal", ["media_player"])

    player = UniversalMediaPlayer(hass, config)
    async_add_entities([player])


class UniversalMediaPlayer(MediaPlayerEntity):
    """Representation of an universal media player."""

    _attr_should_poll = False

    def __init__(
        self,
        hass,
        config,
    ):
        """Initialize the Universal media device."""
        self.hass = hass
        self._name = config.get(CONF_NAME)
        self._children = config.get(CONF_CHILDREN)
        self._cmds = config.get(CONF_COMMANDS)
        self._attrs = {}
        for key, val in config.get(CONF_ATTRS).items():
            attr = list(map(str.strip, val.split("|", 1)))
            if len(attr) == 1:
                attr.append(None)
            self._attrs[key] = attr
        self._child_state = None
        self._state_template_result = None
        self._state_template = config.get(CONF_STATE_TEMPLATE)
        self._device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_unique_id = config.get(CONF_UNIQUE_ID)
        self._browse_media_entity = config.get(CONF_BROWSE_MEDIA_ENTITY)

    async def async_added_to_hass(self) -> None:
        """Subscribe to children and template state changes."""

        @callback
        def _async_on_dependency_update(event):
            """Update ha state when dependencies update."""
            self.async_set_context(event.context)
            self.async_schedule_update_ha_state(True)

        @callback
        def _async_on_template_update(event, updates):
            """Update ha state when dependencies update."""
            result = updates.pop().result

            if isinstance(result, TemplateError):
                self._state_template_result = None
            else:
                self._state_template_result = result

            if event:
                self.async_set_context(event.context)

            self.async_schedule_update_ha_state(True)

        if self._state_template is not None:
            result = async_track_template_result(
                self.hass,
                [TrackTemplate(self._state_template, None)],
                _async_on_template_update,
            )
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, callback(lambda _: result.async_refresh())
            )

            self.async_on_remove(result.async_remove)

        depend = copy(self._children)
        for entity in self._attrs.values():
            depend.append(entity[0])

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, list(set(depend)), _async_on_dependency_update
            )
        )

    def _entity_lkp(self, entity_id, state_attr=None):
        """Look up an entity state."""
        if (state_obj := self.hass.states.get(entity_id)) is None:
            return

        if state_attr:
            return state_obj.attributes.get(state_attr)
        return state_obj.state

    def _override_or_child_attr(self, attr_name):
        """Return either the override or the active child for attr_name."""
        if attr_name in self._attrs:
            return self._entity_lkp(
                self._attrs[attr_name][0], self._attrs[attr_name][1]
            )

        return self._child_attr(attr_name)

    def _child_attr(self, attr_name):
        """Return the active child's attributes."""
        active_child = self._child_state
        return active_child.attributes.get(attr_name) if active_child else None

    async def _async_call_service(
        self, service_name, service_data=None, allow_override=False
    ):
        """Call either a specified or active child's service."""
        if service_data is None:
            service_data = {}

        if allow_override and service_name in self._cmds:
            await async_call_from_config(
                self.hass,
                self._cmds[service_name],
                variables=service_data,
                blocking=True,
                validate_config=False,
            )
            return

        if (active_child := self._child_state) is None:
            # No child to call service on
            return

        service_data[ATTR_ENTITY_ID] = active_child.entity_id

        await self.hass.services.async_call(
            DOMAIN, service_name, service_data, blocking=True, context=self._context
        )

    @property
    def device_class(self) -> MediaPlayerDeviceClass | None:
        """Return the class of this device."""
        return self._device_class

    @property
    def master_state(self):
        """Return the master state for entity or None."""
        if self._state_template is not None:
            return self._state_template_result
        if CONF_STATE in self._attrs:
            master_state = self._entity_lkp(
                self._attrs[CONF_STATE][0], self._attrs[CONF_STATE][1]
            )
            return master_state if master_state else MediaPlayerState.OFF

        return None

    @property
    def name(self):
        """Return the name of universal player."""
        return self._name

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return self._child_attr(ATTR_ASSUMED_STATE)

    @property
    def state(self):
        """Return the current state of media player.

        Off if master state is off
        else Status of first active child
        else master state or off
        """
        master_state = self.master_state  # avoid multiple lookups
        if (master_state == MediaPlayerState.OFF) or (self._state_template is not None):
            return master_state

        if active_child := self._child_state:
            return active_child.state

        return master_state if master_state else MediaPlayerState.OFF

    @property
    def volume_level(self):
        """Volume level of entity specified in attributes or active child."""
        try:
            return float(self._override_or_child_attr(ATTR_MEDIA_VOLUME_LEVEL))
        except (TypeError, ValueError):
            return None

    @property
    def is_volume_muted(self):
        """Boolean if volume is muted."""
        return self._override_or_child_attr(ATTR_MEDIA_VOLUME_MUTED) in [True, STATE_ON]

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self._child_attr(ATTR_MEDIA_CONTENT_ID)

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return self._child_attr(ATTR_MEDIA_CONTENT_TYPE)

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return self._child_attr(ATTR_MEDIA_DURATION)

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._child_attr(ATTR_ENTITY_PICTURE)

    @property
    def entity_picture(self):
        """Return image of the media playing.

        The universal media player doesn't use the parent class logic, since
        the url is coming from child entity pictures which have already been
        sent through the API proxy.
        """
        return self.media_image_url

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._child_attr(ATTR_MEDIA_TITLE)

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        return self._child_attr(ATTR_MEDIA_ARTIST)

    @property
    def media_album_name(self):
        """Album name of current playing media (Music track only)."""
        return self._child_attr(ATTR_MEDIA_ALBUM_NAME)

    @property
    def media_album_artist(self):
        """Album artist of current playing media (Music track only)."""
        return self._child_attr(ATTR_MEDIA_ALBUM_ARTIST)

    @property
    def media_track(self):
        """Track number of current playing media (Music track only)."""
        return self._child_attr(ATTR_MEDIA_TRACK)

    @property
    def media_series_title(self):
        """Return the title of the series of current playing media (TV)."""
        return self._child_attr(ATTR_MEDIA_SERIES_TITLE)

    @property
    def media_season(self):
        """Season of current playing media (TV Show only)."""
        return self._child_attr(ATTR_MEDIA_SEASON)

    @property
    def media_episode(self):
        """Episode of current playing media (TV Show only)."""
        return self._child_attr(ATTR_MEDIA_EPISODE)

    @property
    def media_channel(self):
        """Channel currently playing."""
        return self._child_attr(ATTR_MEDIA_CHANNEL)

    @property
    def media_playlist(self):
        """Title of Playlist currently playing."""
        return self._child_attr(ATTR_MEDIA_PLAYLIST)

    @property
    def app_id(self):
        """ID of the current running app."""
        return self._child_attr(ATTR_APP_ID)

    @property
    def app_name(self):
        """Name of the current running app."""
        return self._child_attr(ATTR_APP_NAME)

    @property
    def sound_mode(self):
        """Return the current sound mode of the device."""
        return self._override_or_child_attr(ATTR_SOUND_MODE)

    @property
    def sound_mode_list(self):
        """List of available sound modes."""
        return self._override_or_child_attr(ATTR_SOUND_MODE_LIST)

    @property
    def source(self):
        """Return the current input source of the device."""
        return self._override_or_child_attr(ATTR_INPUT_SOURCE)

    @property
    def source_list(self):
        """List of available input sources."""
        return self._override_or_child_attr(ATTR_INPUT_SOURCE_LIST)

    @property
    def repeat(self):
        """Boolean if repeating is enabled."""
        return self._override_or_child_attr(ATTR_MEDIA_REPEAT)

    @property
    def shuffle(self):
        """Boolean if shuffling is enabled."""
        return self._override_or_child_attr(ATTR_MEDIA_SHUFFLE)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        flags: MediaPlayerEntityFeature = self._child_attr(
            ATTR_SUPPORTED_FEATURES
        ) or MediaPlayerEntityFeature(0)

        if SERVICE_TURN_ON in self._cmds:
            flags |= MediaPlayerEntityFeature.TURN_ON
        if SERVICE_TURN_OFF in self._cmds:
            flags |= MediaPlayerEntityFeature.TURN_OFF

        if SERVICE_MEDIA_PLAY_PAUSE in self._cmds:
            flags |= MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE
        else:
            if SERVICE_MEDIA_PLAY in self._cmds:
                flags |= MediaPlayerEntityFeature.PLAY
            if SERVICE_MEDIA_PAUSE in self._cmds:
                flags |= MediaPlayerEntityFeature.PAUSE

        if SERVICE_MEDIA_STOP in self._cmds:
            flags |= MediaPlayerEntityFeature.STOP

        if SERVICE_MEDIA_NEXT_TRACK in self._cmds:
            flags |= MediaPlayerEntityFeature.NEXT_TRACK
        if SERVICE_MEDIA_PREVIOUS_TRACK in self._cmds:
            flags |= MediaPlayerEntityFeature.PREVIOUS_TRACK

        if any(cmd in self._cmds for cmd in (SERVICE_VOLUME_UP, SERVICE_VOLUME_DOWN)):
            flags |= MediaPlayerEntityFeature.VOLUME_STEP
        if SERVICE_VOLUME_SET in self._cmds:
            flags |= MediaPlayerEntityFeature.VOLUME_SET

        if SERVICE_VOLUME_MUTE in self._cmds and ATTR_MEDIA_VOLUME_MUTED in self._attrs:
            flags |= MediaPlayerEntityFeature.VOLUME_MUTE

        if (
            SERVICE_SELECT_SOURCE in self._cmds
            and ATTR_INPUT_SOURCE_LIST in self._attrs
        ):
            flags |= MediaPlayerEntityFeature.SELECT_SOURCE

        if SERVICE_PLAY_MEDIA in self._cmds:
            flags |= MediaPlayerEntityFeature.PLAY_MEDIA

        if self._browse_media_entity:
            flags |= MediaPlayerEntityFeature.BROWSE_MEDIA

        if SERVICE_CLEAR_PLAYLIST in self._cmds:
            flags |= MediaPlayerEntityFeature.CLEAR_PLAYLIST

        if SERVICE_SHUFFLE_SET in self._cmds and ATTR_MEDIA_SHUFFLE in self._attrs:
            flags |= MediaPlayerEntityFeature.SHUFFLE_SET

        if SERVICE_REPEAT_SET in self._cmds and ATTR_MEDIA_REPEAT in self._attrs:
            flags |= MediaPlayerEntityFeature.REPEAT_SET

        if (
            SERVICE_SELECT_SOUND_MODE in self._cmds
            and ATTR_SOUND_MODE_LIST in self._attrs
        ):
            flags |= MediaPlayerEntityFeature.SELECT_SOUND_MODE

        return flags

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        active_child = self._child_state
        return {ATTR_ACTIVE_CHILD: active_child.entity_id} if active_child else {}

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return self._child_attr(ATTR_MEDIA_POSITION)

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._child_attr(ATTR_MEDIA_POSITION_UPDATED_AT)

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._async_call_service(SERVICE_TURN_ON, allow_override=True)

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._async_call_service(SERVICE_TURN_OFF, allow_override=True)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        data = {ATTR_MEDIA_VOLUME_MUTED: mute}
        await self._async_call_service(SERVICE_VOLUME_MUTE, data, allow_override=True)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        data = {ATTR_MEDIA_VOLUME_LEVEL: volume}
        await self._async_call_service(SERVICE_VOLUME_SET, data, allow_override=True)

    async def async_media_play(self) -> None:
        """Send play command."""
        await self._async_call_service(SERVICE_MEDIA_PLAY, allow_override=True)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._async_call_service(SERVICE_MEDIA_PAUSE, allow_override=True)

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._async_call_service(SERVICE_MEDIA_STOP, allow_override=True)

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._async_call_service(
            SERVICE_MEDIA_PREVIOUS_TRACK, allow_override=True
        )

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._async_call_service(SERVICE_MEDIA_NEXT_TRACK, allow_override=True)

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        data = {ATTR_MEDIA_SEEK_POSITION: position}
        await self._async_call_service(SERVICE_MEDIA_SEEK, data)

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        data = {ATTR_MEDIA_CONTENT_TYPE: media_type, ATTR_MEDIA_CONTENT_ID: media_id}
        await self._async_call_service(SERVICE_PLAY_MEDIA, data, allow_override=True)

    async def async_volume_up(self) -> None:
        """Turn volume up for media player."""
        await self._async_call_service(SERVICE_VOLUME_UP, allow_override=True)

    async def async_volume_down(self) -> None:
        """Turn volume down for media player."""
        await self._async_call_service(SERVICE_VOLUME_DOWN, allow_override=True)

    async def async_media_play_pause(self) -> None:
        """Play or pause the media player."""
        await self._async_call_service(SERVICE_MEDIA_PLAY_PAUSE, allow_override=True)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        data = {ATTR_SOUND_MODE: sound_mode}
        await self._async_call_service(
            SERVICE_SELECT_SOUND_MODE, data, allow_override=True
        )

    async def async_select_source(self, source: str) -> None:
        """Set the input source."""
        data = {ATTR_INPUT_SOURCE: source}
        await self._async_call_service(SERVICE_SELECT_SOURCE, data, allow_override=True)

    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        await self._async_call_service(SERVICE_CLEAR_PLAYLIST, allow_override=True)

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffling."""
        data = {ATTR_MEDIA_SHUFFLE: shuffle}
        await self._async_call_service(SERVICE_SHUFFLE_SET, data, allow_override=True)

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        data = {ATTR_MEDIA_REPEAT: repeat}
        await self._async_call_service(SERVICE_REPEAT_SET, data, allow_override=True)

    async def async_toggle(self) -> None:
        """Toggle the power on the media player."""
        if SERVICE_TOGGLE in self._cmds:
            await self._async_call_service(SERVICE_TOGGLE, allow_override=True)
        else:
            # Delegate to turn_on or turn_off by default
            await super().async_toggle()

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Return a BrowseMedia instance."""
        entity_id = self._browse_media_entity
        if not entity_id and self._child_state:
            entity_id = self._child_state.entity_id
        component: EntityComponent[MediaPlayerEntity] = self.hass.data[DOMAIN]
        if entity_id and (entity := component.get_entity(entity_id)):
            return await entity.async_browse_media(media_content_type, media_content_id)
        raise NotImplementedError()

    async def async_update(self) -> None:
        """Update state in HA."""
        self._child_state = None
        for child_name in self._children:
            if (child_state := self.hass.states.get(child_name)) and (
                child_state_order := STATES_ORDER_LOOKUP.get(child_state.state, 0)
            ) >= STATES_ORDER_IDLE:
                if self._child_state:
                    if child_state_order > STATES_ORDER_LOOKUP.get(
                        self._child_state.state, 0
                    ):
                        self._child_state = child_state
                else:
                    self._child_state = child_state
