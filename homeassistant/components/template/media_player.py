"""Support for Template media players."""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Self, override

import probatio

from homeassistant.components.media_player import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    ENTITY_ID_FORMAT,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEntity,
    MediaPlayerEntityCapabilityAttribute,
    MediaPlayerEntityFeature,
    MediaPlayerEntityStateAttribute,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_REPEAT,
    CONF_SOURCE,
    CONF_STATE,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import validators as tcv
from .const import DOMAIN
from .coordinator import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA,
    make_template_entity_common_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

CONF_APP_ID = "app_id"
CONF_APP_NAME = "app_name"
CONF_IS_VOLUME_MUTED = "is_volume_muted"
CONF_MEDIA_ALBUM_ARTIST = "media_album_artist"
CONF_MEDIA_ALBUM_NAME = "media_album_name"
CONF_MEDIA_ARTIST = "media_artist"
CONF_MEDIA_CHANNEL = "media_channel"
CONF_MEDIA_CONTENT_ID = "media_content_id"
CONF_MEDIA_CONTENT_TYPE = "media_content_type"
CONF_MEDIA_DURATION = "media_duration"
CONF_MEDIA_EPISODE = "media_episode"
CONF_MEDIA_IMAGE_URL = "media_image_url"
CONF_MEDIA_PLAYLIST = "media_playlist"
CONF_MEDIA_POSITION = "media_position"
CONF_MEDIA_SEASON = "media_season"
CONF_MEDIA_SERIES_TITLE = "media_series_title"
CONF_MEDIA_TITLE = "media_title"
CONF_MEDIA_TRACK = "media_track"
CONF_SHUFFLE = "shuffle"
CONF_SOUND_MODE = "sound_mode"
CONF_SOUND_MODE_LIST = "sound_mode_list"
CONF_SOURCE_LIST = "source_list"
CONF_VOLUME_LEVEL = "volume_level"
CONF_VOLUME_UP_AND_DOWN = "volume_up_and_down"

DEFAULT_NAME = "Template Media Player"

SCRIPT_FIELDS = (
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_PLAY_MEDIA,
    SERVICE_REPEAT_SET,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    SERVICE_SHUFFLE_SET,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)

STRING_TEMPLATES = (
    (CONF_APP_ID, "_attr_app_id"),
    (CONF_APP_NAME, "_attr_app_name"),
    (CONF_MEDIA_ALBUM_ARTIST, "_attr_media_album_artist"),
    (CONF_MEDIA_ALBUM_NAME, "_attr_media_album_name"),
    (CONF_MEDIA_ARTIST, "_attr_media_artist"),
    (CONF_MEDIA_CHANNEL, "_attr_media_channel"),
    (CONF_MEDIA_CONTENT_ID, "_attr_media_content_id"),
    (CONF_MEDIA_CONTENT_TYPE, "_attr_media_content_type"),
    (CONF_MEDIA_EPISODE, "_attr_media_episode"),
    (CONF_MEDIA_IMAGE_URL, "_attr_media_image_url"),
    (CONF_MEDIA_PLAYLIST, "_attr_media_playlist"),
    (CONF_MEDIA_SEASON, "_attr_media_season"),
    (CONF_MEDIA_SERIES_TITLE, "_attr_media_series_title"),
    (CONF_MEDIA_TITLE, "_attr_media_title"),
)

# Media metadata restored for trigger entities that have not rendered yet.
RESTORED_MEDIA_TEMPLATES = (
    *STRING_TEMPLATES,
    (CONF_MEDIA_DURATION, "_attr_media_duration"),
    (CONF_MEDIA_POSITION, "_attr_media_position"),
    (CONF_MEDIA_TRACK, "_attr_media_track"),
)

# Deprecated states must not be produced by new entities.
DEPRECATED_STATES = (MediaPlayerState("standby"),)

MEDIA_PLAYER_COMMON_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        probatio.Optional(CONF_STATE): cv.template,
        probatio.Optional(CONF_IS_VOLUME_MUTED): cv.template,
        probatio.Optional(CONF_MEDIA_DURATION): cv.template,
        probatio.Optional(CONF_MEDIA_POSITION): cv.template,
        probatio.Optional(CONF_MEDIA_TRACK): cv.template,
        probatio.Optional(CONF_REPEAT): cv.template,
        probatio.Optional(CONF_SHUFFLE): cv.template,
        probatio.Optional(CONF_SOUND_MODE): cv.template,
        probatio.Optional(CONF_SOUND_MODE_LIST): cv.template,
        probatio.Optional(CONF_SOURCE): cv.template,
        probatio.Optional(CONF_SOURCE_LIST): cv.template,
        probatio.Optional(CONF_VOLUME_LEVEL): cv.template,
        **{probatio.Optional(option): cv.template for option, _ in STRING_TEMPLATES},
        **{
            probatio.Optional(action): cv.SCRIPT_SCHEMA
            for action in SCRIPT_FIELDS
            if action not in (SERVICE_VOLUME_DOWN, SERVICE_VOLUME_UP)
        },
        probatio.Inclusive(
            SERVICE_VOLUME_DOWN, CONF_VOLUME_UP_AND_DOWN
        ): cv.SCRIPT_SCHEMA,
        probatio.Inclusive(
            SERVICE_VOLUME_UP, CONF_VOLUME_UP_AND_DOWN
        ): cv.SCRIPT_SCHEMA,
    }
)

_MEDIA_PLAYER_VALIDATION = (
    tcv.requires_option(CONF_SOURCE, CONF_SOURCE_LIST),
    tcv.requires_option(SERVICE_SELECT_SOURCE, CONF_SOURCE_LIST),
    tcv.requires_option(CONF_SOUND_MODE, CONF_SOUND_MODE_LIST),
    tcv.requires_option(SERVICE_SELECT_SOUND_MODE, CONF_SOUND_MODE_LIST),
)

_BLOCKED_ATTRIBUTES = tcv.BlockedTemplateAttributes(
    attributes=(MediaPlayerEntityCapabilityAttribute, MediaPlayerEntityStateAttribute),
    device_class=True,
)

MEDIA_PLAYER_YAML_SCHEMA = probatio.All(
    MEDIA_PLAYER_COMMON_SCHEMA.extend(TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA).extend(
        make_template_entity_common_schema(
            MEDIA_PLAYER_DOMAIN, DEFAULT_NAME, _BLOCKED_ATTRIBUTES
        ).schema
    ),
    *_MEDIA_PLAYER_VALIDATION,
)

MEDIA_PLAYER_CONFIG_ENTRY_SCHEMA = MEDIA_PLAYER_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template media players."""
    await async_setup_template_platform(
        hass,
        MEDIA_PLAYER_DOMAIN,
        config,
        StateMediaPlayerEntity,
        TriggerMediaPlayerEntity,
        async_add_entities,
        discovery_info,
        script_options=SCRIPT_FIELDS,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    await async_setup_template_entry(
        hass,
        config_entry,
        async_add_entities,
        StateMediaPlayerEntity,
        MEDIA_PLAYER_CONFIG_ENTRY_SCHEMA,
        script_options=SCRIPT_FIELDS,
    )


@callback
def async_create_preview_media_player(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateMediaPlayerEntity:
    """Create a preview."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        StateMediaPlayerEntity,
        MEDIA_PLAYER_CONFIG_ENTRY_SCHEMA,
    )


@dataclass(kw_only=True)
class MediaPlayerExtraStoredData(ExtraStoredData):
    """Holds extra stored data for template media player entities."""

    is_volume_muted: bool | None
    media: dict[str, str | int | None]
    media_position_updated_at: datetime | None
    repeat: RepeatMode | str | None
    shuffle: bool | None
    sound_mode: str | None
    sound_mode_list: list[str] | None
    source: str | None
    source_list: list[str] | None
    volume_level: float | None

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the media player data."""
        data = asdict(self)
        if self.media_position_updated_at is not None:
            data["media_position_updated_at"] = (
                self.media_position_updated_at.isoformat()
            )
        return data

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize a stored media player state from a dict."""
        try:
            repeat: RepeatMode | None = None
            if _repeat := restored["repeat"]:
                repeat = RepeatMode(_repeat)

            media_position_updated_at: datetime | None = None
            if _updated_at := restored["media_position_updated_at"]:
                media_position_updated_at = dt_util.parse_datetime(_updated_at)

            return cls(
                is_volume_muted=restored["is_volume_muted"],
                media={
                    option: restored["media"][option]
                    for option, _ in RESTORED_MEDIA_TEMPLATES
                },
                media_position_updated_at=media_position_updated_at,
                repeat=repeat,
                shuffle=restored["shuffle"],
                sound_mode=restored["sound_mode"],
                sound_mode_list=restored["sound_mode_list"],
                source=restored["source"],
                source_list=restored["source_list"],
                volume_level=restored["volume_level"],
            )
        except KeyError, ValueError:
            return None


class AbstractTemplateMediaPlayer(
    AbstractTemplateEntity, MediaPlayerEntity, RestoreEntity
):
    """Representation of a template media player features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True
    _state_option = CONF_STATE
    _restore_state_extra_data = MediaPlayerExtraStoredData
    _restore_state_properties = ("_attr_state",)
    _blocked_attributes = _BLOCKED_ATTRIBUTES

    # The super init is not called because TemplateEntity
    # and TriggerEntity will call
    # AbstractTemplateEntity.__init__. This ensures that
    # the __init__ on AbstractTemplateEntity is not
    # called twice.
    def __init__(self, name: str, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._rendered_media_position: int | None = None

        self.setup_state_template(
            "_attr_state",
            tcv.strenum(
                self,
                CONF_STATE,
                MediaPlayerState,
                MediaPlayerState.ON,
                MediaPlayerState.OFF,
                deprecated_enums=DEPRECATED_STATES,
            ),
            self._update_player_state,
        )

        for option, attr in STRING_TEMPLATES:
            self.setup_template(
                option,
                attr,
                tcv.string(self, option),
                self._update_media_content_id
                if option == CONF_MEDIA_CONTENT_ID
                else None,
            )

        self.setup_template(
            CONF_VOLUME_LEVEL,
            "_attr_volume_level",
            tcv.number(self, CONF_VOLUME_LEVEL, 0.0, 1.0),
        )
        self.setup_template(
            CONF_IS_VOLUME_MUTED,
            "_attr_is_volume_muted",
            tcv.boolean(self, CONF_IS_VOLUME_MUTED),
        )
        self.setup_template(
            CONF_MEDIA_DURATION,
            "_attr_media_duration",
            tcv.number(self, CONF_MEDIA_DURATION, 0, return_type=int),
        )
        self.setup_template(
            CONF_MEDIA_POSITION,
            "_attr_media_position",
            tcv.number(self, CONF_MEDIA_POSITION, 0, return_type=int),
            self._update_media_position,
        )
        self.setup_template(
            CONF_MEDIA_TRACK,
            "_attr_media_track",
            tcv.number(self, CONF_MEDIA_TRACK, 0, return_type=int),
        )
        self.setup_template(
            CONF_SHUFFLE,
            "_attr_shuffle",
            tcv.boolean(self, CONF_SHUFFLE),
        )
        self.setup_template(
            CONF_REPEAT,
            "_attr_repeat",
            tcv.strenum(self, CONF_REPEAT, RepeatMode),
        )

        for list_option, list_attr, option, attr in (
            (
                CONF_SOURCE_LIST,
                "_attr_source_list",
                CONF_SOURCE,
                "_attr_source",
            ),
            (
                CONF_SOUND_MODE_LIST,
                "_attr_sound_mode_list",
                CONF_SOUND_MODE,
                "_attr_sound_mode",
            ),
        ):
            self.setup_list_item_templates(
                list_option,
                list_attr,
                tcv.list_of_strings(self, list_option),
                option,
                attr,
                tcv.item_in_list(
                    self, option, list_attr, list_option, stringify_result=True
                ),
            )

        for attr, option, action in (
            ("_attr_volume_level", CONF_VOLUME_LEVEL, SERVICE_VOLUME_SET),
            ("_attr_is_volume_muted", CONF_IS_VOLUME_MUTED, SERVICE_VOLUME_MUTE),
            ("_attr_source", CONF_SOURCE, SERVICE_SELECT_SOURCE),
            ("_attr_sound_mode", CONF_SOUND_MODE, SERVICE_SELECT_SOUND_MODE),
            ("_attr_shuffle", CONF_SHUFFLE, SERVICE_SHUFFLE_SET),
            ("_attr_repeat", CONF_REPEAT, SERVICE_REPEAT_SET),
        ):
            self.add_assumed_attribute(attr, option, action)

        self._attr_supported_features = MediaPlayerEntityFeature(0)
        for action_id, supported_feature in (
            (SERVICE_CLEAR_PLAYLIST, MediaPlayerEntityFeature.CLEAR_PLAYLIST),
            (SERVICE_MEDIA_NEXT_TRACK, MediaPlayerEntityFeature.NEXT_TRACK),
            (SERVICE_MEDIA_PAUSE, MediaPlayerEntityFeature.PAUSE),
            (SERVICE_MEDIA_PLAY, MediaPlayerEntityFeature.PLAY),
            (SERVICE_MEDIA_PREVIOUS_TRACK, MediaPlayerEntityFeature.PREVIOUS_TRACK),
            (SERVICE_MEDIA_SEEK, MediaPlayerEntityFeature.SEEK),
            (SERVICE_MEDIA_STOP, MediaPlayerEntityFeature.STOP),
            (SERVICE_PLAY_MEDIA, MediaPlayerEntityFeature.PLAY_MEDIA),
            (SERVICE_REPEAT_SET, MediaPlayerEntityFeature.REPEAT_SET),
            (SERVICE_SELECT_SOUND_MODE, MediaPlayerEntityFeature.SELECT_SOUND_MODE),
            (SERVICE_SELECT_SOURCE, MediaPlayerEntityFeature.SELECT_SOURCE),
            (SERVICE_SHUFFLE_SET, MediaPlayerEntityFeature.SHUFFLE_SET),
            (SERVICE_TURN_OFF, MediaPlayerEntityFeature.TURN_OFF),
            (SERVICE_TURN_ON, MediaPlayerEntityFeature.TURN_ON),
            (SERVICE_VOLUME_DOWN, MediaPlayerEntityFeature.VOLUME_STEP),
            (SERVICE_VOLUME_MUTE, MediaPlayerEntityFeature.VOLUME_MUTE),
            (SERVICE_VOLUME_SET, MediaPlayerEntityFeature.VOLUME_SET),
            (SERVICE_VOLUME_UP, MediaPlayerEntityFeature.VOLUME_STEP),
        ):
            if (action_config := config.get(action_id)) is not None:
                self.add_script(action_id, action_config, name, DOMAIN)
                self._attr_supported_features |= supported_feature

    @callback
    def _update_player_state(self, state: MediaPlayerState | None) -> None:
        """Update the state and rebase the position timestamp on transitions."""
        # Resuming at an unchanged position must not extrapolate over the pause.
        if state != self._attr_state and self._attr_media_position is not None:
            now = dt_util.utcnow()
            if (
                self._attr_state == MediaPlayerState.PLAYING
                and (updated_at := self._attr_media_position_updated_at) is not None
            ):
                # Keep the playback elapsed since the last position sample.
                position = self._attr_media_position + int(
                    (now - updated_at).total_seconds()
                )
                if self._attr_media_duration is not None:
                    position = min(position, self._attr_media_duration)
                self._attr_media_position = position
            self._attr_media_position_updated_at = now
        self._attr_state = state

    @callback
    def _update_media_content_id(self, content_id: str | None) -> None:
        """Update the media item and restart the position clock for a new item."""
        # An unchanged position sample does not update the timestamp, so a new
        # item would otherwise inherit the elapsed time of the previous one.
        if (
            content_id != self._attr_media_content_id
            and self._attr_media_position is not None
        ):
            self._attr_media_position = self._rendered_media_position
            self._attr_media_position_updated_at = (
                None if self._rendered_media_position is None else dt_util.utcnow()
            )
        self._attr_media_content_id = content_id

    @callback
    def _update_media_position(self, position: int | None) -> None:
        """Update the position and the time it was last valid."""
        # Trigger entities re-render unchanged samples, which must not undo the
        # position kept by a state transition or reset the clock. Template errors
        # and restoring change the position without updating the last sample.
        if position == self._rendered_media_position and (position is None) == (
            self._attr_media_position is None
        ):
            return
        self._rendered_media_position = position
        self._attr_media_position = position
        self._attr_media_position_updated_at = (
            None if position is None else dt_util.utcnow()
        )

    @property
    def _media_image_picture(self) -> str | None:
        """Return the proxied media image while the player is on."""
        if self.state == MediaPlayerState.OFF:
            return None
        return self.media_image_local

    async def _async_run_action(
        self,
        action_id: str,
        run_variables: dict[str, Any] | None = None,
        state: MediaPlayerState | None = None,
    ) -> None:
        """Run an action script and optimistically update the state."""
        if script := self._action_scripts.get(action_id):
            await self.async_run_script(
                script, run_variables=run_variables, context=self._context
            )
        if state is not None and self._attr_assumed_state:
            self._update_player_state(state)
            self.async_write_ha_state()

    @override
    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._async_run_action(SERVICE_TURN_ON, state=MediaPlayerState.ON)

    @override
    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._async_run_action(SERVICE_TURN_OFF, state=MediaPlayerState.OFF)

    @override
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._async_run_action(SERVICE_MEDIA_PLAY, state=MediaPlayerState.PLAYING)

    @override
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._async_run_action(SERVICE_MEDIA_PAUSE, state=MediaPlayerState.PAUSED)

    @override
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._async_run_action(SERVICE_MEDIA_STOP, state=MediaPlayerState.IDLE)

    @override
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._async_run_action(SERVICE_MEDIA_NEXT_TRACK)

    @override
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._async_run_action(SERVICE_MEDIA_PREVIOUS_TRACK)

    @override
    async def async_clear_playlist(self) -> None:
        """Clear the playlist."""
        await self._async_run_action(SERVICE_CLEAR_PLAYLIST)

    @override
    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self._async_run_action(SERVICE_MEDIA_SEEK, {"seek_position": position})

    @override
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        await self._async_run_action(
            SERVICE_PLAY_MEDIA,
            {
                "media_content_type": media_type,
                "media_content_id": media_id,
                **kwargs,
            },
            MediaPlayerState.PLAYING,
        )

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        await self._async_run_action(SERVICE_VOLUME_SET, {"volume_level": volume})
        self.write_assumed_attribute(CONF_VOLUME_LEVEL, volume)

    @override
    async def async_volume_up(self) -> None:
        """Turn the volume up."""
        if SERVICE_VOLUME_UP not in self._action_scripts:
            await super().async_volume_up()
            return
        await self._async_run_action(SERVICE_VOLUME_UP)

    @override
    async def async_volume_down(self) -> None:
        """Turn the volume down."""
        if SERVICE_VOLUME_DOWN not in self._action_scripts:
            await super().async_volume_down()
            return
        await self._async_run_action(SERVICE_VOLUME_DOWN)

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the volume."""
        await self._async_run_action(SERVICE_VOLUME_MUTE, {"is_volume_muted": mute})
        self.write_assumed_attribute(CONF_IS_VOLUME_MUTED, mute)

    @override
    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        await self._async_run_action(SERVICE_SELECT_SOURCE, {"source": source})
        self.write_assumed_attribute(CONF_SOURCE, source)

    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select a sound mode."""
        await self._async_run_action(
            SERVICE_SELECT_SOUND_MODE, {"sound_mode": sound_mode}
        )
        self.write_assumed_attribute(CONF_SOUND_MODE, sound_mode)

    @override
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable or disable shuffle."""
        await self._async_run_action(SERVICE_SHUFFLE_SET, {"shuffle": shuffle})
        self.write_assumed_attribute(CONF_SHUFFLE, shuffle)

    @override
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set the repeat mode."""
        await self._async_run_action(SERVICE_REPEAT_SET, {"repeat": repeat})
        self.write_assumed_attribute(CONF_REPEAT, repeat)

    @override
    def restore_last_state_state(self, last_state: State) -> bool:
        """Restore the state from the last state."""
        if (
            last_state.state in MediaPlayerState
            and last_state.state not in DEPRECATED_STATES
        ):
            self._attr_state = MediaPlayerState(last_state.state)
            return True

        return False

    @property
    @override
    def extra_restore_state_data(self) -> MediaPlayerExtraStoredData:
        """Return media player specific state data to be restored."""
        return MediaPlayerExtraStoredData(
            is_volume_muted=self._attr_is_volume_muted,
            media={
                option: getattr(self, attr) for option, attr in RESTORED_MEDIA_TEMPLATES
            },
            media_position_updated_at=self._attr_media_position_updated_at,
            repeat=self._attr_repeat,
            shuffle=self._attr_shuffle,
            sound_mode=self._attr_sound_mode,
            sound_mode_list=self._attr_sound_mode_list,
            source=self._attr_source,
            source_list=self._attr_source_list,
            volume_level=self._attr_volume_level,
        )

    @override
    def restore_extra_data(self, extra_data: MediaPlayerExtraStoredData) -> None:
        """Restore the extra data."""
        self._attr_is_volume_muted = extra_data.is_volume_muted
        for option, attr in RESTORED_MEDIA_TEMPLATES:
            setattr(self, attr, extra_data.media[option])
        self._attr_media_position_updated_at = extra_data.media_position_updated_at
        self._attr_repeat = extra_data.repeat
        self._attr_shuffle = extra_data.shuffle
        self._attr_sound_mode = extra_data.sound_mode
        self._attr_sound_mode_list = extra_data.sound_mode_list
        self._attr_source = extra_data.source
        self._attr_source_list = extra_data.source_list
        self._attr_volume_level = extra_data.volume_level


class StateMediaPlayerEntity(TemplateEntity, AbstractTemplateMediaPlayer):
    """Representation of a template media player."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the media player."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None
        AbstractTemplateMediaPlayer.__init__(self, name, config)

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the media image, falling back to the picture option."""
        return self._media_image_picture or self._attr_entity_picture


class TriggerMediaPlayerEntity(TriggerEntity, AbstractTemplateMediaPlayer):
    """Media player entity based on trigger data."""

    domain = MEDIA_PLAYER_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        AbstractTemplateMediaPlayer.__init__(self, name, config)

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the media image, falling back to the picture option."""
        return self._media_image_picture or super().entity_picture
