"""Media player platform for iNet Radio."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
import logging
from typing import Any, Concatenate

from inet_control import VOLUME_MAX, Radio, RadioManager

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import INetConfigEntry
from .const import CONF_MODEL_DESCRIPTION, DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

SOURCE_AUX = "AUX"
SOURCE_UPNP = "UPnP"


def _handle_errors[
    _R,
    **_P,
](
    func: Callable[Concatenate[INetMediaPlayer, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[INetMediaPlayer, _P], Coroutine[Any, Any, _R]]:
    """Wrap entity action to raise HomeAssistantError on OSError."""

    @wraps(func)
    async def wrapper(self: INetMediaPlayer, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except OSError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err

    return wrapper


async def async_setup_entry(
    hass: HomeAssistant,
    entry: INetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up iNet Radio media player from a config entry."""
    manager: RadioManager = entry.runtime_data
    host = entry.data[CONF_HOST]
    radio = manager.radios[host]
    async_add_entities([INetMediaPlayer(entry, manager, radio)])


class INetMediaPlayer(MediaPlayerEntity):
    """Representation of an iNet Radio media player."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(
        self, entry: INetConfigEntry, manager: RadioManager, radio: Radio
    ) -> None:
        """Initialize the iNet Radio media player."""
        self._manager = manager
        self._radio = radio
        unique_id = entry.unique_id
        assert unique_id is not None
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=radio.name or f"iNet Radio ({radio.ip})",
            manufacturer="Busch-Jaeger",
            model=entry.data.get(CONF_MODEL_DESCRIPTION),
            sw_version=radio.sw_version or None,
            connections={(CONNECTION_NETWORK_MAC, radio.mac)} if radio.mac else set(),
        )
        self._update_attrs()

    @callback
    def _handle_state_update(self) -> None:
        """Handle state updates from the radio."""
        self._update_attrs()
        self.async_write_ha_state()

    @callback
    def _update_attrs(self) -> None:
        """Update entity attributes from radio state."""
        radio = self._radio

        if not radio.available:
            self._attr_available = False
            return

        self._attr_available = True

        if radio.power:
            if radio.playing_mode:
                self._attr_state = MediaPlayerState.PLAYING
            else:
                self._attr_state = MediaPlayerState.IDLE
        else:
            self._attr_state = MediaPlayerState.OFF

        self._attr_volume_level = radio.volume / VOLUME_MAX
        self._attr_is_volume_muted = radio.muted
        self._attr_media_title = radio.playing_station_name or None

        # Build source list from station presets + AUX + UPnP
        sources: list[str] = []
        for station in radio.stations:
            if station.name:
                sources.append(station.name)
            else:
                sources.append(f"Station {station.channel}")
        sources.append(SOURCE_AUX)
        sources.append(SOURCE_UPNP)
        self._attr_source_list = sources

        # Current source
        match radio.playing_mode:
            case "STATION":
                self._attr_source = radio.playing_station_name or None
            case "AUX":
                self._attr_source = SOURCE_AUX
            case "UPNP":
                self._attr_source = SOURCE_UPNP
            case _:
                self._attr_source = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to radio state updates."""
        await super().async_added_to_hass()
        unsub = self._radio.register_callback(self._handle_state_update)
        self.async_on_remove(unsub)

    @_handle_errors
    async def async_turn_on(self) -> None:
        """Turn the radio on."""
        await self._manager.turn_on(self._radio)

    @_handle_errors
    async def async_turn_off(self) -> None:
        """Turn the radio off."""
        await self._manager.turn_off(self._radio)

    @_handle_errors
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0.0 to 1.0)."""
        await self._manager.set_volume(self._radio, round(volume * VOLUME_MAX))

    @_handle_errors
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the radio."""
        if mute:
            await self._manager.mute(self._radio)
        else:
            await self._manager.unmute(self._radio)

    @_handle_errors
    async def async_volume_up(self) -> None:
        """Increase volume by one step."""
        await self._manager.volume_up(self._radio)

    @_handle_errors
    async def async_volume_down(self) -> None:
        """Decrease volume by one step."""
        await self._manager.volume_down(self._radio)

    @_handle_errors
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if source == SOURCE_AUX:
            await self._manager.play_aux(self._radio)
            return
        if source == SOURCE_UPNP:
            await self._manager.play_upnp(self._radio)
            return

        # Match source name to a station preset
        for station in self._radio.stations:
            if source in (station.name, f"Station {station.channel}"):
                await self._manager.play_station(self._radio, station.channel)
                return

        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_source",
            translation_placeholders={"source": source},
        )
