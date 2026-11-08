"""Support for LG soundbars."""

from collections.abc import Awaitable
import contextlib
from typing import Any, override

import aiotemescal
from aiotemescal import TemescalConnectionError

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LGSoundbarConfigEntry
from .const import DOMAIN

EQUIVALENT_FUNCTIONS = (
    ("Optical/HDMI ARC", "E-ARC", "ARC", "LG Optical", "Optical", "Optical2"),
    ("HDMI", "HDMI2", "HDMI3"),
    ("USB", "USB2"),
    ("Bluetooth", "Portable"),
    ("Wi-Fi", "Chromecast", "Spotify"),
)


def _display_name(names: list[str], index: int) -> str:
    """Return the display name for an index.

    Newer models report indices past the end of the library name tables.
    Naming those keeps them selectable instead of silently dropping them.
    """
    if index < len(names):
        return names[index]

    return f"Unknown ({index})"


def _offered_names(names: list[str], offered: list[int]) -> list[str]:
    """Return the display names of the offered indices."""
    return sorted(_display_name(names, index) for index in offered)


def _index_for_name(names: list[str], offered: list[int], name: str) -> int:
    """Return the index a display name refers to.

    Indices the library cannot name are only known through the offered list, so
    they are resolved from there; anything else resolves against the library.
    """
    for index in offered:
        if _display_name(names, index) == name:
            return index

    return names.index(name)


def _offered_equivalent(function: str, offered: list[int]) -> str | None:
    """Return an offered function from the same group as the given one."""
    group = next((names for names in EQUIVALENT_FUNCTIONS if function in names), ())
    return next(
        (name for name in group if aiotemescal.functions.index(name) in offered), None
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LGSoundbarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up media_player from a config entry created in the integrations UI."""
    async_add_entities([LGDevice(config_entry)])


class LGDevice(MediaPlayerEntity):
    """Representation of an LG soundbar device."""

    _attr_should_poll = False
    # Default to ON to ensure compatibility with models
    # that don't send a powerstatus message
    _attr_state = MediaPlayerState.ON
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
    )
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: LGSoundbarConfigEntry) -> None:
        """Initialize the LG speakers."""
        self._entry = entry
        self._client = entry.runtime_data
        unique_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = unique_id

        self._volume = 0
        self._volume_max = 0
        self._function = -1
        self._functions: list[int] = []
        self._equaliser = -1
        self._equalisers: list[int] = []
        self._mute = False
        self._support_play_control = False
        # Starts out matching the ON default of _attr_state, for the same reason
        self._device_on = True
        self._stream_type = 0
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)}, name=entry.data[CONF_HOST]
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Follow the messages and the connection state of the device."""
        self.async_on_remove(self._client.subscribe(self._handle_event))
        self.async_on_remove(self._client.subscribe_connection(self._handle_connection))
        self._attr_available = self._client.connected

    @callback
    def _handle_connection(self, connected: bool) -> None:
        """Track availability; the client fetches the state before connecting."""
        self._attr_available = connected
        self.async_write_ha_state()

    async def _async_get_play(self) -> None:
        """Ask for the play info, whose answer arrives as a message."""
        # A lost connection is reported through _handle_connection
        with contextlib.suppress(TemescalConnectionError):
            await self._client.get_play()

    async def _async_send(self, command: Awaitable[None]) -> None:
        """Send a command on behalf of an action."""
        try:
            await command
        except TemescalConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

    @callback
    def _handle_event(self, response: dict[str, Any]) -> None:
        """Handle messages from the speakers."""
        data = response.get("data") or {}
        if response["msg"] == "EQ_VIEW_INFO":
            self._update_equalisers(data)
        elif response["msg"] == "SPK_LIST_VIEW_INFO":
            if "i_vol" in data:
                self._volume = data["i_vol"]
            if "i_vol_max" in data:
                self._volume_max = data["i_vol_max"]
            if "b_mute" in data:
                self._mute = data["b_mute"]
            if "i_curr_func" in data:
                self._function = data["i_curr_func"]
            if "b_powerstatus" in data:
                self._device_on = data["b_powerstatus"]
                if not data["b_powerstatus"]:
                    self._attr_state = MediaPlayerState.OFF
                # Reported again on reconnections, which must not end playback
                elif self._attr_state not in (
                    MediaPlayerState.PLAYING,
                    MediaPlayerState.PAUSED,
                ):
                    self._attr_state = MediaPlayerState.ON
        elif response["msg"] == "FUNC_VIEW_INFO":
            if "i_curr_func" in data:
                self._function = data["i_curr_func"]
            if "ai_func_list" in data:
                self._functions = data["ai_func_list"]
        elif response["msg"] == "SETTING_VIEW_INFO":
            if "i_curr_eq" in data:
                self._equaliser = data["i_curr_eq"]
            if "s_user_name" in data:
                self._attr_name = data["s_user_name"]
        elif response["msg"] == "PLAY_INFO":
            self._update_playinfo(data)

        self.async_write_ha_state()

    def _update_equalisers(self, data: dict[str, Any]) -> None:
        """Update the equalisers."""
        if "ai_eq_list" in data:
            self._equalisers = data["ai_eq_list"]
        if "i_curr_eq" in data:
            self._equaliser = data["i_curr_eq"]

    def _update_playinfo(self, data: dict[str, Any]) -> None:
        """Update the player info."""
        if "i_stream_type" in data:
            if self._stream_type != data["i_stream_type"]:
                self._stream_type = data["i_stream_type"]
                # Ask device for current play info when stream type changed.
                self._entry.async_create_background_task(
                    self.hass, self._async_get_play(), "lg_soundbar play info"
                )
            if data["i_stream_type"] == 0:
                # If the stream type is 0 (aka the soundbar
                # is used as an actual soundbar) the last
                # track info should be cleared and the
                # state should only be on or off, as all
                # playing/paused are not applicable
                self._attr_media_image_url = None
                self._attr_media_artist = None
                self._attr_media_title = None
                if self._device_on:
                    self._attr_state = MediaPlayerState.ON
                else:
                    self._attr_state = MediaPlayerState.OFF
        if "i_play_ctrl" in data:
            if self._device_on and self._stream_type != 0:
                if data["i_play_ctrl"] == 0:
                    self._attr_state = MediaPlayerState.PLAYING
                else:
                    self._attr_state = MediaPlayerState.PAUSED
        if "s_albumart" in data:
            self._attr_media_image_url = data["s_albumart"].strip() or None
        if "s_artist" in data:
            self._attr_media_artist = data["s_artist"].strip() or None
        if "s_title" in data:
            self._attr_media_title = data["s_title"].strip() or None
        if "b_support_play_ctrl" in data:
            self._support_play_control = data["b_support_play_ctrl"]

    @property
    @override
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported.

        Models that do not report their power state also ignore the power key.
        """
        if self._client.reports_power:
            return (
                self._attr_supported_features
                | MediaPlayerEntityFeature.TURN_ON
                | MediaPlayerEntityFeature.TURN_OFF
            )
        return self._attr_supported_features

    @property
    @override
    def volume_level(self) -> float:
        """Volume level of the media player (0..1)."""
        if self._volume_max != 0:
            return self._volume / self._volume_max
        return 0

    @property
    @override
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    @override
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        if self._equaliser == -1:
            return None
        return _display_name(aiotemescal.equalisers, self._equaliser)

    @property
    @override
    def sound_mode_list(self) -> list[str]:
        """Return the available sound modes."""
        return _offered_names(aiotemescal.equalisers, self._equalisers)

    @property
    @override
    def source(self) -> str | None:
        """Return the current input source."""
        if self._function == -1:
            return None
        function = _display_name(aiotemescal.functions, self._function)
        if self._function in self._functions:
            return function
        return _offered_equivalent(function, self._functions) or function

    @property
    @override
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return _offered_names(aiotemescal.functions, self._functions)

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._async_send(self._client.set_volume(int(volume * self._volume_max)))

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self._async_send(self._client.set_mute(mute))

    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self._async_send(
            self._client.set_func(
                _index_for_name(aiotemescal.functions, self._functions, source)
            )
        )

    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Set Sound Mode for Receiver.."""
        await self._async_send(
            self._client.set_eq(
                _index_for_name(aiotemescal.equalisers, self._equalisers, sound_mode)
            )
        )

    @override
    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._async_send(self._client.set_power(True))

    @override
    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._async_send(self._client.set_power(False))

    @override
    async def async_media_play(self) -> None:
        """Send play command."""
        if self._support_play_control:
            await self._async_send(self._client.set_play_ctrl(True))

    @override
    async def async_media_pause(self) -> None:
        """Send pause command."""
        if self._support_play_control:
            await self._async_send(self._client.set_play_ctrl(False))
