"""Support for Yamaha Receivers."""

from __future__ import annotations

import logging
from typing import Any

import requests
import rxv
from rxv import RXV
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    BRAND,
    CURSOR_TYPE_DOWN,
    CURSOR_TYPE_LEFT,
    CURSOR_TYPE_RETURN,
    CURSOR_TYPE_RIGHT,
    CURSOR_TYPE_SELECT,
    CURSOR_TYPE_UP,
    DEFAULT_NAME,
    DOMAIN,
    OPTION_INPUT_SOURCES,
    OPTION_INPUT_SOURCES_IGNORE,
    SERVICE_ENABLE_OUTPUT,
    SERVICE_MENU_CURSOR,
    SERVICE_SELECT_SCENE,
)

_LOGGER = logging.getLogger(__name__)

ATTR_CURSOR = "cursor"
ATTR_ENABLED = "enabled"
ATTR_PORT = "port"

ATTR_SCENE = "scene"

CURSOR_TYPE_MAP = {
    CURSOR_TYPE_DOWN: rxv.RXV.menu_down.__name__,
    CURSOR_TYPE_LEFT: rxv.RXV.menu_left.__name__,
    CURSOR_TYPE_RETURN: rxv.RXV.menu_return.__name__,
    CURSOR_TYPE_RIGHT: rxv.RXV.menu_right.__name__,
    CURSOR_TYPE_SELECT: rxv.RXV.menu_sel.__name__,
    CURSOR_TYPE_UP: rxv.RXV.menu_up.__name__,
}

SUPPORT_YAMAHA = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Yamaha zones based on a config entry."""
    device: rxv.RXV = hass.data[DOMAIN][entry.entry_id]

    media_players: list[Entity] = []

    for zctrl in device.zone_controllers():
        entity = YamahaDeviceZone(
            entry.data.get(CONF_NAME, DEFAULT_NAME),
            zctrl,
            entry.options.get(OPTION_INPUT_SOURCES_IGNORE),
            entry.options.get(OPTION_INPUT_SOURCES),
        )

        media_players.append(entity)

    async_add_entities(media_players)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Yamaha platform."""
    if config.get(CONF_HOST):
        if hass.config_entries.async_entries(DOMAIN) and config[CONF_HOST] not in [
            entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
        ]:
            _LOGGER.error(
                "Configuration in configuration.yaml is not supported anymore. "
                "Please add this device using the config flow: %s",
                config[CONF_HOST],
            )
        else:
            _LOGGER.warning(
                "Configuration in configuration.yaml is deprecated. Use the config flow instead"
            )

            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=config
                )
            )
    else:
        _LOGGER.error(
            "Configuration in configuration.yaml is not supported anymore. "
            "Please add this device using the config flow"
        )

    # Register Service 'select_scene'
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SELECT_SCENE,
        {vol.Required(ATTR_SCENE): cv.string},
        "set_scene",
    )
    # Register Service 'enable_output'
    platform.async_register_entity_service(
        SERVICE_ENABLE_OUTPUT,
        {vol.Required(ATTR_ENABLED): cv.boolean, vol.Required(ATTR_PORT): cv.string},
        "enable_output",
    )
    # Register Service 'menu_cursor'
    platform.async_register_entity_service(
        SERVICE_MENU_CURSOR,
        {vol.Required(ATTR_CURSOR): vol.In(CURSOR_TYPE_MAP)},
        YamahaDeviceZone.menu_cursor.__name__,
    )


class YamahaDeviceZone(MediaPlayerEntity):
    """Representation of a Yamaha device zone."""

    _reverse_mapping: dict[str, str]

    def __init__(
        self,
        name: str,
        zctrl: RXV,
        source_ignore: list[str] | None,
        source_names: dict[str, str] | None,
    ) -> None:
        """Initialize the Yamaha Receiver."""
        self.zctrl = zctrl
        self._attr_is_volume_muted = False
        self._attr_volume_level = 0
        self._attr_state = MediaPlayerState.OFF
        self._source_ignore: list[str] = source_ignore or []
        self._source_names: dict[str, str] = source_names or {}
        self._playback_support = None
        self._is_playback_supported = False
        self._play_status = None
        self._name = name
        self._zone = zctrl.zone
        if self.zctrl.serial_number is not None:
            # Since not all receivers will have a serial number and set a unique id
            # the default name of the integration may not be changed
            # to avoid a breaking change.
            self._attr_unique_id = f"{self.zctrl.serial_number}_{self._zone}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._attr_unique_id)},
                manufacturer=BRAND,
                name=name + " " + zctrl.zone,
                model=zctrl.model_name,
            )

    def update(self) -> None:
        """Get the latest details from the device."""
        try:
            self._play_status = self.zctrl.play_status()
        except requests.exceptions.ConnectionError:
            _LOGGER.debug("Receiver is offline: %s", self._name)
            self._attr_available = False
            return

        self._attr_available = True
        if self.zctrl.on:
            if self._play_status is None:
                self._attr_state = MediaPlayerState.ON
            elif self._play_status.playing:
                self._attr_state = MediaPlayerState.PLAYING
            else:
                self._attr_state = MediaPlayerState.IDLE
        else:
            self._attr_state = MediaPlayerState.OFF

        self._attr_is_volume_muted = self.zctrl.mute
        self._attr_volume_level = (self.zctrl.volume / 100) + 1

        if self.source_list is None:
            self.build_source_list()

        current_source = self.zctrl.input
        self._attr_source = self._source_names.get(current_source, current_source)
        self._playback_support = self.zctrl.get_playback_support()
        self._is_playback_supported = self.zctrl.is_playback_supported(
            self._attr_source
        )
        surround_programs = self.zctrl.surround_programs()
        if surround_programs:
            self._attr_sound_mode = self.zctrl.surround_program
            self._attr_sound_mode_list = surround_programs
        else:
            self._attr_sound_mode = None
            self._attr_sound_mode_list = None

    def build_source_list(self) -> None:
        """Build the source list."""
        self._reverse_mapping = {
            alias: source for source, alias in self._source_names.items()
        }

        self._attr_source_list = sorted(
            self._source_names.get(source, source)
            for source in self.zctrl.inputs()
            if source not in self._source_ignore
        )

    @property
    def name(self) -> str:
        """Return the name of the device."""
        name = self._name
        if self._zone != "Main_Zone":
            # Zone will be one of Main_Zone, Zone_2, Zone_3
            name += f" {self._zone.replace('_', ' ')}"
        return name

    @property
    def zone_id(self) -> str:
        """Return a zone_id to ensure 1 media player per zone."""
        return f"{self.zctrl.ctrl_url}:{self._zone}"

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        supported_features = SUPPORT_YAMAHA

        supports = self._playback_support
        mapping = {
            "play": (
                MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PLAY_MEDIA
            ),
            "pause": MediaPlayerEntityFeature.PAUSE,
            "stop": MediaPlayerEntityFeature.STOP,
            "skip_f": MediaPlayerEntityFeature.NEXT_TRACK,
            "skip_r": MediaPlayerEntityFeature.PREVIOUS_TRACK,
        }
        for attr, feature in mapping.items():
            if getattr(supports, attr, False):
                supported_features |= feature
        return supported_features

    def turn_off(self) -> None:
        """Turn off media player."""
        self.zctrl.on = False

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        zone_vol = 100 - (volume * 100)
        negative_zone_vol = -zone_vol
        self.zctrl.volume = negative_zone_vol

    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        self.zctrl.mute = mute

    def turn_on(self) -> None:
        """Turn the media player on."""
        self.zctrl.on = True
        self._attr_volume_level = (self.zctrl.volume / 100) + 1

    def media_play(self) -> None:
        """Send play command."""
        self._call_playback_function(self.zctrl.play, "play")

    def media_pause(self) -> None:
        """Send pause command."""
        self._call_playback_function(self.zctrl.pause, "pause")

    def media_stop(self) -> None:
        """Send stop command."""
        self._call_playback_function(self.zctrl.stop, "stop")

    def media_previous_track(self) -> None:
        """Send previous track command."""
        self._call_playback_function(self.zctrl.previous, "previous track")

    def media_next_track(self) -> None:
        """Send next track command."""
        self._call_playback_function(self.zctrl.next, "next track")

    def _call_playback_function(self, function, function_text):
        try:
            function()
        except rxv.exceptions.ResponseException:
            _LOGGER.warning("Failed to execute %s on %s", function_text, self._name)

    def select_source(self, source: str) -> None:
        """Select input source."""
        self.zctrl.input = self._reverse_mapping.get(source, source)

    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media from an ID.

        This exposes a pass through for various input sources in the
        Yamaha to direct play certain kinds of media. media_type is
        treated as the input type that we are setting, and media id is
        specific to it.
        For the NET RADIO mediatype the format for ``media_id`` is a
        "path" in your vtuner hierarchy. For instance:
        ``Bookmarks>Internet>Radio Paradise``. The separators are
        ``>`` and the parts of this are navigated by name behind the
        scenes. There is a looping construct built into the yamaha
        library to do this with a fallback timeout if the vtuner
        service is unresponsive.
        NOTE: this might take a while, because the only API interface
        for setting the net radio station emulates button pressing and
        navigating through the net radio menu hierarchy. And each sub
        menu must be fetched by the receiver from the vtuner service.
        """
        if media_type == "NET RADIO":
            self.zctrl.net_radio(media_id)

    def enable_output(self, port: str, enabled: bool) -> None:
        """Enable or disable an output port.."""
        self.zctrl.enable_output(port, enabled)

    def menu_cursor(self, cursor: str) -> None:
        """Press a menu cursor button."""
        getattr(self.zctrl, CURSOR_TYPE_MAP[cursor])()

    def set_scene(self, scene: str) -> None:
        """Set the current scene."""
        try:
            self.zctrl.scene = scene
        except AssertionError:
            _LOGGER.warning("Scene '%s' does not exist!", scene)

    def select_sound_mode(self, sound_mode: str) -> None:
        """Set Sound Mode for Receiver.."""
        self.zctrl.surround_program = sound_mode

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media."""
        if self._play_status is not None:
            return self._play_status.artist
        return None

    @property
    def media_album_name(self) -> str | None:
        """Album of current playing media."""
        if self._play_status is not None:
            return self._play_status.album
        return None

    @property
    def media_content_type(self) -> MediaType | None:
        """Content type of current playing media."""
        # Loose assumption that if playback is supported, we are playing music
        if self._is_playback_supported:
            return MediaType.MUSIC
        return None

    @property
    def media_title(self) -> str | None:
        """Artist of current playing media."""
        if self._play_status is not None:
            song = self._play_status.song
            station = self._play_status.station

            # If both song and station is available, print both, otherwise
            # just the one we have.
            if song and station:
                return f"{station}: {song}"

            return song or station
        return None
