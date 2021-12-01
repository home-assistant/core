"""Support for interface with an LG webOS Smart TV."""
import asyncio
from contextlib import suppress
from datetime import timedelta
from functools import wraps
import logging
from typing import Any
from typing_extensions import TypeGuard

from aiopylgtv import PyLGTVCmdException, PyLGTVPairException, WebOsClient
from websockets.exceptions import ConnectionClosed

from homeassistant import util
from homeassistant.components.plex.media_player import PlexMediaPlayer
from homeassistant.helpers.entity_platform import EntityPlatform, async_get_platforms
from homeassistant.components.media_player import DEVICE_CLASS_TV, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_CHANNEL,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from .const import (
    ATTR_PAYLOAD,
    ATTR_SOUND_OUTPUT,
    CONF_ON_ACTION,
    CONF_PLEX_ENTITY,
    CONF_SOURCES,
    DOMAIN,
    LIVE_TV_APP_ID,
    PLEX_SOURCE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CUSTOMIZE,
    CONF_HOST,
    CONF_NAME,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.script import Script
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.components.media_player.const import DOMAIN as DOMAIN_MEDIA_PLAYER

_LOGGER = logging.getLogger(__name__)

SUPPORT_WEBOSTV = (
    SUPPORT_TURN_OFF
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_SELECT_SOUND_MODE
    | SUPPORT_STOP
    | SUPPORT_SEEK
)

SUPPORT_WEBOSTV_VOLUME = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_STEP
# support browse media when plex is the active source
SUPPORT_PLEX = SUPPORT_BROWSE_MEDIA

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    """Set up the LG webOS Smart TV platform."""

    if discovery_info is None:
        return

    host = discovery_info[CONF_HOST]
    name = discovery_info[CONF_NAME]
    customize = discovery_info[CONF_CUSTOMIZE]
    turn_on_action = discovery_info.get(CONF_ON_ACTION)

    client = hass.data[DOMAIN][host]["client"]
    on_script = Script(hass, turn_on_action, name, DOMAIN) if turn_on_action else None

    # Get the plex entity id from the discovery config
    plex_entity_id = discovery_info.get(CONF_PLEX_ENTITY)

    entity = LgWebOSMediaPlayerEntity(
        client, name, customize, on_script, plex_entity_id
    )

    async_add_entities([entity], update_before_add=False)


def cmd(func):
    """Catch command exceptions."""

    @wraps(func)
    async def wrapper(obj, *args, **kwargs):
        """Wrap all command methods."""
        try:
            await func(obj, *args, **kwargs)
        except (
            asyncio.TimeoutError,
            asyncio.CancelledError,
            PyLGTVCmdException,
        ) as exc:
            # If TV is off, we expect calls to fail.
            if obj.state == STATE_OFF:
                level = logging.INFO
            else:
                level = logging.ERROR
            _LOGGER.log(
                level,
                "Error calling %s on entity %s: %r",
                func.__name__,
                obj.entity_id,
                exc,
            )

    return wrapper


class LgWebOSMediaPlayerEntity(MediaPlayerEntity):
    """Representation of a LG webOS Smart TV."""

    def __init__(
        self,
        client: WebOsClient,
        name: str,
        customize,
        on_script=None,
        plex_entity_id: str = None,
    ):
        """Initialize the webos device."""
        self._client: WebOsClient = client
        self._name = name
        self._unique_id = client.client_key
        self._customize = customize
        self._on_script = on_script
        self._plex_entity_id: str = plex_entity_id

        # Assume that the TV is not paused
        self._paused = False
        # Assume that the TV is stopped
        self._stopped = True

        self._current_source = None
        self._source_list: dict = {}

    async def async_added_to_hass(self):
        """Connect and subscribe to dispatcher signals and state updates."""
        async_dispatcher_connect(self.hass, DOMAIN, self.async_signal_handler)

        await self._client.register_state_update_callback(
            self.async_handle_state_update
        )

    async def async_will_remove_from_hass(self):
        """Call disconnect on removal."""
        self._client.unregister_state_update_callback(self.async_handle_state_update)

    async def async_signal_handler(self, data):
        """Handle domain-specific signal by calling appropriate method."""
        if (entity_ids := data[ATTR_ENTITY_ID]) == ENTITY_MATCH_NONE:
            return

        if entity_ids == ENTITY_MATCH_ALL or self.entity_id in entity_ids:
            params = {
                key: value
                for key, value in data.items()
                if key not in ["entity_id", "method"]
            }
            await getattr(self, data["method"])(**params)

    async def async_handle_state_update(self):
        """Update state from WebOsClient."""
        self.update_sources()

        self.async_write_ha_state()

    def update_sources(self):
        """Update list of sources from current source, apps, inputs and configured list."""
        source_list = self._source_list
        self._source_list = {}
        conf_sources = self._customize[CONF_SOURCES]

        found_live_tv = False
        for app in self._client.apps.values():
            if app["id"] == LIVE_TV_APP_ID:
                found_live_tv = True
            if app["id"] == self._client.current_appId:
                self._current_source = app["title"]
                self._source_list[app["title"]] = app
            elif (
                not conf_sources
                or app["id"] in conf_sources
                or any(word in app["title"] for word in conf_sources)
                or any(word in app["id"] for word in conf_sources)
            ):
                self._source_list[app["title"]] = app

        for source in self._client.inputs.values():
            if source["appId"] == LIVE_TV_APP_ID:
                found_live_tv = True
            if source["appId"] == self._client.current_appId:
                self._current_source = source["label"]
                self._source_list[source["label"]] = source
            elif (
                not conf_sources
                or source["label"] in conf_sources
                or any(source["label"].find(word) != -1 for word in conf_sources)
            ):
                self._source_list[source["label"]] = source

        # special handling of live tv since this might not appear in the app or input lists in some cases
        if not found_live_tv:
            app = {"id": LIVE_TV_APP_ID, "title": "Live TV"}
            if LIVE_TV_APP_ID == self._client.current_appId:
                self._current_source = app["title"]
                self._source_list["Live TV"] = app
            elif (
                not conf_sources
                or app["id"] in conf_sources
                or any(word in app["title"] for word in conf_sources)
                or any(word in app["id"] for word in conf_sources)
            ):
                self._source_list["Live TV"] = app
        if not self._source_list and source_list:
            self._source_list = source_list

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    async def async_update(self):
        """Connect."""
        if not self._client.is_connected():
            with suppress(
                OSError,
                ConnectionClosed,
                ConnectionRefusedError,
                asyncio.TimeoutError,
                asyncio.CancelledError,
                PyLGTVPairException,
                PyLGTVCmdException,
            ):
                await self._client.connect()

    def plex_entity(self) -> PlexMediaPlayer:
        """Gets the plex entity object"""

        if not self._plex_entity_id:
            return None

        platforms: list[EntityPlatform] = async_get_platforms(self.hass, "plex")

        platform: EntityPlatform
        for platform in platforms:
            if not platform.domain == DOMAIN_MEDIA_PLAYER:
                continue

            entity_id: str
            entity: Entity
            for entity_id, entity in platform.entities.items():
                if not entity_id == self._plex_entity_id:
                    continue

                return entity

        return None

    def can_proxy_to_plex(self) -> bool:
        """Gets whether methods and attributes can currently be proxied to the specified plex entity"""

        if not self._client.is_on:
            return False

        if not self.source == PLEX_SOURCE:
            return False

        if not self._plex_entity_id:
            return False

        if self.plex_entity() is None:
            return False

        return True

    @property
    def unique_id(self):
        """Return the unique id of the device."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the device."""
        return DEVICE_CLASS_TV

    @property
    def state(self):
        """Return the state of the device."""

        if self.can_proxy_to_plex():
            return self.plex_entity().state

        if not self._client.is_on:
            return STATE_OFF
        elif self._stopped:
            return STATE_ON
        elif self._paused:
            return STATE_PAUSED
        else:
            return STATE_PLAYING

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._client.muted

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._client.volume is not None:
            return self._client.volume / 100.0

        return None

    @property
    def source(self):
        """Return the current input source."""
        return self._current_source

    @property
    def source_list(self):
        """List of available input sources."""
        return sorted(self._source_list)

    @property
    def media_content_type(self):
        """Content type of current playing media."""

        if self.can_proxy_to_plex():
            return self.plex_entity().media_content_type

        if self._client.current_appId == LIVE_TV_APP_ID:
            return MEDIA_TYPE_CHANNEL

        return None

    @property
    def media_content_id(self):
        """Content ID of current playing media."""

        if not self.can_proxy_to_plex():
            return None

        return self.plex_entity().media_content_id

    @property
    def media_title(self):
        """Title of current playing media."""

        if self.can_proxy_to_plex():
            return self.plex_entity().media_title

        if (self._client.current_appId == LIVE_TV_APP_ID) and (
            self._client.current_channel is not None
        ):
            return self._client.current_channel.get("channelName")
        return None

    @property
    def media_album_artist(self):
        """Gets the currently playing album's artist"""

        if not self.can_proxy_to_plex():
            return None

        return self.plex_entity().media_album_artist

    @property
    def media_album_name(self):
        """Gets the currently playing album's name"""

        if not self.can_proxy_to_plex():
            return None

        return self.plex_entity().media_album_name

    @property
    def media_artist(self):
        """Gets the currently playing music's artist"""

        if not self.can_proxy_to_plex():
            return None

        return self.plex_entity().media_artist

    @property
    def media_duration(self):
        """Gets the currently playing media's duration"""

        if not self.can_proxy_to_plex():
            return None

        return self.plex_entity().media_duration

    @property
    def media_episode(self):
        """Gets the currently playing tv episode's number"""

        if not self.can_proxy_to_plex():
            return None

        return self.plex_entity().media_episode

    @property
    def media_image_hash(self):
        """Gets the currently playing media's image hash"""

        if not self.can_proxy_to_plex():
            return None

        return self.plex_entity().media_image_hash

    @property
    def media_position(self):
        """Gets the currently playing media's position"""

        if not self.can_proxy_to_plex():
            return None

        return self.plex_entity().media_position

    @property
    def media_season(self):
        """Gets the currently playing tv episode's season number"""

        if not self.can_proxy_to_plex():
            return None

        return self.plex_entity().media_season

    @property
    def media_position_updated_at(self):
        """Gets the currently playing media's last position update time"""

        if not self.can_proxy_to_plex():
            return None

        return self.plex_entity().media_position_updated_at

    @property
    def media_track(self):
        """Gets the currently playing music's track number"""

        if not self.can_proxy_to_plex():
            return None

        return self.plex_entity().media_track

    @property
    def media_series_title(self):
        """Gets the currently playing tv series title"""

        if not self.can_proxy_to_plex():
            return None

        return self.plex_entity().media_series_title

    @property
    def media_playlist(self):
        """Gets the currently playing media playlist name"""

        if not self.can_proxy_to_plex():
            return None

        return self.plex_entity().media_playlist

    @property
    def entity_picture(self):
        """Gets the currently playing media's picture"""

        if self.can_proxy_to_plex():
            return self.plex_entity().entity_picture

        if self._client.current_appId in self._client.apps:
            icon = self._client.apps[self._client.current_appId]["largeIcon"]
            if not icon.startswith("http"):
                icon = self._client.apps[self._client.current_appId]["icon"]
            return icon

        return None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        supported = SUPPORT_WEBOSTV

        if self._client.sound_output in ("external_arc", "external_speaker"):
            supported = supported | SUPPORT_WEBOSTV_VOLUME
        elif self._client.sound_output != "lineout":
            supported = supported | SUPPORT_WEBOSTV_VOLUME | SUPPORT_VOLUME_SET

        if self._on_script:
            supported = supported | SUPPORT_TURN_ON

        if self.can_proxy_to_plex():
            supported = supported | SUPPORT_PLEX

        return supported

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        if self._client.sound_output is None and self.state == STATE_OFF:
            return {}
        return {ATTR_SOUND_OUTPUT: self._client.sound_output}

    @property
    def sound_mode(self):
        """Gets the currently selected sound output"""
        if self._client.sound_output is None and self.state == STATE_OFF:
            return None
        return self._client.sound_output

    @property
    def sound_mode_list(self):
        """Gets the list of supported sound outputs"""
        return [
            "tv_speaker",
            "external_arc",
            "external_optical",
            "bt_soundbar",
            "external_speaker",
            "lineout",
            "headphone",
            "tv_external_speaker",
            "tv_speaker_headphone",
        ]

    @cmd
    async def async_turn_off(self):
        """Turn off media player."""
        self._paused = False
        self._stopped = True
        await self._client.power_off()
        self.async_schedule_update_ha_state()

    async def async_turn_on(self):
        """Turn on the media player."""
        if self._on_script:
            await self._on_script.async_run(context=self._context)
        self._paused = False
        self._stopped = True
        self.async_schedule_update_ha_state()

    @cmd
    async def async_volume_up(self):
        """Volume up the media player."""
        await self._client.volume_up()
        self.async_schedule_update_ha_state()

    @cmd
    async def async_volume_down(self):
        """Volume down media player."""
        await self._client.volume_down()
        self.async_schedule_update_ha_state()

    @cmd
    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        tv_volume = int(round(volume * 100))
        await self._client.set_volume(tv_volume)
        self.async_schedule_update_ha_state()

    @cmd
    async def async_mute_volume(self, mute):
        """Send mute command."""
        await self._client.set_mute(mute)
        self.async_schedule_update_ha_state()

    @cmd
    async def async_select_sound_mode(self, sound_mode):
        """Select the sound mode."""
        await self._client.change_sound_output(sound_mode)
        self.async_schedule_update_ha_state()

    @cmd
    async def async_media_play_pause(self):
        """Simulate play pause media player."""

        if self.can_proxy_to_plex():
            plex_entity = self.plex_entity()
            await plex_entity.async_media_play_pause()
            self.async_schedule_update_ha_state()
            return

        if self._paused:
            await self.async_media_play()
        else:
            await self.async_media_pause()

    @cmd
    async def async_select_source(self, source):
        """Select input source."""
        if (source_dict := self._source_list.get(source)) is None:
            _LOGGER.warning("Source %s not found for %s", source, self.name)
            return
        if source_dict.get("title"):
            await self._client.launch_app(source_dict["id"])
        elif source_dict.get("label"):
            await self._client.set_input(source_dict["id"])

        self.async_schedule_update_ha_state()

    @cmd
    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        _LOGGER.debug("Call play media type <%s>, Id <%s>", media_type, media_id)

        if self.can_proxy_to_plex():
            plex_entity = self.plex_entity()
            await plex_entity.async_play_media(media_type, media_id, **kwargs)
            self.async_schedule_update_ha_state()
            return

        if media_type == MEDIA_TYPE_CHANNEL:
            _LOGGER.debug("Searching channel")
            partial_match_channel_id = None
            perfect_match_channel_id = None

            for channel in self._client.channels:
                if media_id == channel["channelNumber"]:
                    perfect_match_channel_id = channel["channelId"]
                    continue

                if media_id.lower() == channel["channelName"].lower():
                    perfect_match_channel_id = channel["channelId"]
                    continue

                if media_id.lower() in channel["channelName"].lower():
                    partial_match_channel_id = channel["channelId"]

            if perfect_match_channel_id is not None:
                _LOGGER.info(
                    "Switching to channel <%s> with perfect match",
                    perfect_match_channel_id,
                )
                await self._client.set_channel(perfect_match_channel_id)
            elif partial_match_channel_id is not None:
                _LOGGER.info(
                    "Switching to channel <%s> with partial match",
                    partial_match_channel_id,
                )
                await self._client.set_channel(partial_match_channel_id)

        self.async_schedule_update_ha_state()

    @cmd
    async def async_media_play(self):
        """Send play command."""

        if self.can_proxy_to_plex():
            plex_entity = self.plex_entity()
            await plex_entity.async_media_play()
            self.async_schedule_update_ha_state()
            return

        self._stopped = False
        self._paused = False
        await self._client.play()
        self.async_schedule_update_ha_state()

    @cmd
    async def async_media_pause(self):
        """Send media pause command to media player."""

        if self.can_proxy_to_plex():
            plex_entity = self.plex_entity()
            await plex_entity.async_media_pause()
            self.async_schedule_update_ha_state()
            return

        if self._stopped:
            return

        self._paused = True
        await self._client.pause()
        self.async_schedule_update_ha_state()

    @cmd
    async def async_media_stop(self):
        """Send stop command to media player."""

        if self.can_proxy_to_plex():
            plex_entity = self.plex_entity()
            await plex_entity.async_media_stop()
            self.async_schedule_update_ha_state()
            return

        self._paused = False
        self._stopped = True
        await self._client.stop()
        self.async_schedule_update_ha_state()

    @cmd
    async def async_media_next_track(self):
        """Send next track command."""

        if self.can_proxy_to_plex():
            plex_entity = self.plex_entity()
            await plex_entity.async_media_next_track()
            self.async_schedule_update_ha_state()
            return

        current_input = self._client.get_input()
        if current_input == LIVE_TV_APP_ID:
            await self._client.channel_up()
        else:
            await self._client.fast_forward()

        self.async_schedule_update_ha_state()

    @cmd
    async def async_media_previous_track(self):
        """Send the previous track command."""

        if self.can_proxy_to_plex():
            plex_entity = self.plex_entity()
            await plex_entity.async_media_previous_track()
            self.async_schedule_update_ha_state()
            return

        current_input = self._client.get_input()
        if current_input == LIVE_TV_APP_ID:
            await self._client.channel_down()
        else:
            await self._client.rewind()

        self.async_schedule_update_ha_state()

    @cmd
    async def async_button(self, button):
        """Send a button press."""
        await self._client.button(button)
        self.async_schedule_update_ha_state()

    @cmd
    async def async_command(self, command, **kwargs):
        """Send a command."""
        await self._client.request(command, payload=kwargs.get(ATTR_PAYLOAD))
        self.async_schedule_update_ha_state()

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Returns the browse media object"""

        if not self.can_proxy_to_plex():
            return None

        return await self.plex_entity().async_browse_media(
            media_content_type, media_content_id
        )

    async def async_media_seek(self, position):
        """Seeks the currently playing media to the provided position"""

        if not self.can_proxy_to_plex():
            return

        await self.plex_entity().async_media_seek(position)
        self.async_schedule_update_ha_state()
