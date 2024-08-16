"""Support for Yamaha Receivers."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

import requests
import rxv
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CURSOR_TYPE_DOWN,
    CURSOR_TYPE_LEFT,
    CURSOR_TYPE_RETURN,
    CURSOR_TYPE_RIGHT,
    CURSOR_TYPE_SELECT,
    CURSOR_TYPE_UP,
    DISCOVER_TIMEOUT,
    DOMAIN,
    KNOWN_ZONES,
    SERVICE_ENABLE_OUTPUT,
    SERVICE_MENU_CURSOR,
    SERVICE_SELECT_SCENE,
)

_LOGGER = logging.getLogger(__name__)

ATTR_CURSOR = "cursor"
ATTR_ENABLED = "enabled"
ATTR_PORT = "port"

ATTR_SCENE = "scene"

CONF_SOURCE_IGNORE = "source_ignore"
CONF_SOURCE_NAMES = "source_names"
CONF_ZONE_IGNORE = "zone_ignore"
CONF_ZONE_NAMES = "zone_names"

CURSOR_TYPE_MAP = {
    CURSOR_TYPE_DOWN: rxv.RXV.menu_down.__name__,
    CURSOR_TYPE_LEFT: rxv.RXV.menu_left.__name__,
    CURSOR_TYPE_RETURN: rxv.RXV.menu_return.__name__,
    CURSOR_TYPE_RIGHT: rxv.RXV.menu_right.__name__,
    CURSOR_TYPE_SELECT: rxv.RXV.menu_sel.__name__,
    CURSOR_TYPE_UP: rxv.RXV.menu_up.__name__,
}
DEFAULT_NAME = "Yamaha Receiver"

SUPPORT_YAMAHA = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
)

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_SOURCE_IGNORE, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_ZONE_IGNORE, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_SOURCE_NAMES, default={}): {cv.string: cv.string},
        vol.Optional(CONF_ZONE_NAMES, default={}): {cv.string: cv.string},
    }
)


class YamahaConfigInfo:
    """Configuration Info for Yamaha Receivers."""

    def __init__(
        self, config: ConfigType, discovery_info: DiscoveryInfoType | None
    ) -> None:
        """Initialize the Configuration Info for Yamaha Receiver."""
        self.name = config.get(CONF_NAME)
        self.host = config.get(CONF_HOST)
        self.ctrl_url: str | None = f"http://{self.host}:80/YamahaRemoteControl/ctrl"
        self.source_ignore = config.get(CONF_SOURCE_IGNORE)
        self.source_names = config.get(CONF_SOURCE_NAMES)
        self.zone_ignore = config.get(CONF_ZONE_IGNORE)
        self.zone_names = config.get(CONF_ZONE_NAMES)
        self.from_discovery = False
        _LOGGER.debug("Discovery Info: %s", discovery_info)
        if discovery_info is not None:
            self.name = discovery_info.get("name")
            self.model = discovery_info.get("model_name")
            self.ctrl_url = discovery_info.get("control_url")
            self.desc_url = discovery_info.get("description_url")
            self.zone_ignore = []
            self.from_discovery = True


def _discovery(config_info):
    """Discover list of zone controllers from configuration in the network."""
    if config_info.from_discovery:
        _LOGGER.debug("Discovery Zones")
        zones = rxv.RXV(
            config_info.ctrl_url,
            model_name=config_info.model,
            friendly_name=config_info.name,
            unit_desc_url=config_info.desc_url,
        ).zone_controllers()
    elif config_info.host is None:
        _LOGGER.debug("Config No Host Supplied Zones")
        zones = []
        for recv in rxv.find(DISCOVER_TIMEOUT):
            zones.extend(recv.zone_controllers())
    else:
        _LOGGER.debug("Config Zones")
        zones = None

        # Fix for upstream issues in rxv.find() with some hardware.
        with contextlib.suppress(AttributeError, ValueError):
            for recv in rxv.find(DISCOVER_TIMEOUT):
                _LOGGER.debug(
                    "Found Serial %s %s %s",
                    recv.serial_number,
                    recv.ctrl_url,
                    recv.zone,
                )
                if recv.ctrl_url == config_info.ctrl_url:
                    _LOGGER.debug(
                        "Config Zones Matched Serial %s: %s",
                        recv.ctrl_url,
                        recv.serial_number,
                    )
                    zones = rxv.RXV(
                        config_info.ctrl_url,
                        friendly_name=config_info.name,
                        serial_number=recv.serial_number,
                        model_name=recv.model_name,
                    ).zone_controllers()
                    break

        if not zones:
            _LOGGER.debug("Config Zones Fallback")
            zones = rxv.RXV(config_info.ctrl_url, config_info.name).zone_controllers()

    _LOGGER.debug("Returned _discover zones: %s", zones)
    return zones


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Yamaha platform."""
    # Keep track of configured receivers so that we don't end up
    # discovering a receiver dynamically that we have static config
    # for. Map each device from its zone_id .
    known_zones = hass.data.setdefault(DOMAIN, {KNOWN_ZONES: set()})[KNOWN_ZONES]
    _LOGGER.debug("Known receiver zones: %s", known_zones)

    # Get the Infos for configuration from config (YAML) or Discovery
    config_info = YamahaConfigInfo(config=config, discovery_info=discovery_info)
    # Async check if the Receivers are there in the network
    try:
        zone_ctrls = await hass.async_add_executor_job(_discovery, config_info)
    except requests.exceptions.ConnectionError as ex:
        raise PlatformNotReady(f"Issue while connecting to {config_info.name}") from ex

    entities = []
    for zctrl in zone_ctrls:
        _LOGGER.debug("Receiver zone: %s serial %s", zctrl.zone, zctrl.serial_number)
        if config_info.zone_ignore and zctrl.zone in config_info.zone_ignore:
            _LOGGER.debug("Ignore receiver zone: %s %s", config_info.name, zctrl.zone)
            continue

        entity = YamahaDeviceZone(
            config_info.name,
            zctrl,
            config_info.source_ignore,
            config_info.source_names,
            config_info.zone_names,
        )

        # Only add device if it's not already added
        if entity.zone_id not in known_zones:
            known_zones.add(entity.zone_id)
            entities.append(entity)
        else:
            _LOGGER.debug(
                "Ignoring duplicate zone: %s %s", config_info.name, zctrl.zone
            )

    async_add_entities(entities)

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

    def __init__(self, name, zctrl, source_ignore, source_names, zone_names):
        """Initialize the Yamaha Receiver."""
        self.zctrl = zctrl
        self._attr_is_volume_muted = False
        self._attr_volume_level = 0
        self._attr_state = MediaPlayerState.OFF
        self._source_ignore = source_ignore or []
        self._source_names = source_names or {}
        self._zone_names = zone_names or {}
        self._reverse_mapping = None
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

    def build_source_list(self):
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
    def name(self):
        """Return the name of the device."""
        name = self._name
        zone_name = self._zone_names.get(self._zone, self._zone)
        if zone_name != "Main_Zone":
            # Zone will be one of Main_Zone, Zone_2, Zone_3
            name += f" {zone_name.replace('_', ' ')}"
        return name

    @property
    def zone_id(self):
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

    def enable_output(self, port, enabled):
        """Enable or disable an output port.."""
        self.zctrl.enable_output(port, enabled)

    def menu_cursor(self, cursor):
        """Press a menu cursor button."""
        getattr(self.zctrl, CURSOR_TYPE_MAP[cursor])()

    def set_scene(self, scene):
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
