"""Media player platform for the Samsung ExLink integration."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
from functools import wraps
from typing import Any

from samsung_exlink import MAX_VOLUME, CommandRejected, InputSource, TVState

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SamsungExLinkConfigEntry

# Samsung TVs do not push state over RS-232, so the entity is polled.
SCAN_INTERVAL = timedelta(seconds=5)
PARALLEL_UPDATES = 1

INPUT_SOURCE_SAMSUNG_TO_HA: dict[InputSource, str] = {
    InputSource.TV: "tv",
    InputSource.AV1: "av1",
    InputSource.AV2: "av2",
    InputSource.AV3: "av3",
    InputSource.S_VIDEO1: "s_video1",
    InputSource.S_VIDEO2: "s_video2",
    InputSource.S_VIDEO3: "s_video3",
    InputSource.COMPONENT1: "component1",
    InputSource.COMPONENT2: "component2",
    InputSource.COMPONENT3: "component3",
    InputSource.PC1: "pc1",
    InputSource.PC2: "pc2",
    InputSource.PC3: "pc3",
    InputSource.HDMI1: "hdmi1",
    InputSource.HDMI2: "hdmi2",
    InputSource.HDMI3: "hdmi3",
    InputSource.HDMI4: "hdmi4",
    InputSource.DVI1: "dvi1",
    InputSource.DVI2: "dvi2",
    InputSource.DVI3: "dvi3",
    InputSource.RVU: "rvu",
}
INPUT_SOURCE_HA_TO_SAMSUNG: dict[str, InputSource] = {
    value: key for key, value in INPUT_SOURCE_SAMSUNG_TO_HA.items()
}

_BASE_SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
)


def catch_command_errors[**_P](
    func: Callable[_P, Coroutine[Any, Any, None]],
) -> Callable[_P, Coroutine[Any, Any, None]]:
    """Translate Samsung library errors raised by an action into HomeAssistantError."""

    @wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(*args, **kwargs)
        except CommandRejected as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={"error": str(err)},
            ) from err
        except (ConnectionError, OSError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    return wrapper


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SamsungExLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Samsung ExLink media player."""
    async_add_entities([SamsungExLinkMediaPlayer(config_entry)])


class SamsungExLinkMediaPlayer(MediaPlayerEntity):
    """Representation of a Samsung TV controlled over ExLink (RS-232)."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "tv"
    _attr_source_list = sorted(INPUT_SOURCE_SAMSUNG_TO_HA.values())

    def __init__(self, config_entry: SamsungExLinkConfigEntry) -> None:
        """Initialize the media player."""
        self._tv = config_entry.runtime_data
        self._attr_unique_id = config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Samsung",
        )
        self._async_update_from_state(self._tv.state)

    async def async_added_to_hass(self) -> None:
        """Subscribe to TV state updates."""
        self.async_on_remove(self._tv.subscribe(self._async_on_state_update))

    async def async_update(self) -> None:
        """Poll the TV for its current state."""
        await self._tv.refresh()

    @callback
    def _async_on_state_update(self, state: TVState | None) -> None:
        """Handle a state update from the TV."""
        if state is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._async_update_from_state(state)
        self.async_write_ha_state()

    @callback
    def _async_update_from_state(self, state: TVState) -> None:
        """Update entity attributes from a TV state snapshot."""
        if state.power is None:
            self._attr_state = None
        else:
            self._attr_state = (
                MediaPlayerState.ON if state.power else MediaPlayerState.OFF
            )

        # A standby TV only accepts power-on over RS-232; source, volume, and
        # mute commands time out. Those controls (and their attributes) are
        # therefore only exposed while the TV is on, and volume/mute also
        # require the value to be known.
        features = _BASE_SUPPORTED_FEATURES
        if state.power:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
            source = state.input_source
            self._attr_source = (
                INPUT_SOURCE_SAMSUNG_TO_HA.get(source) if source else None
            )

            if state.volume is None:
                self._attr_volume_level = None
            else:
                features |= (
                    MediaPlayerEntityFeature.VOLUME_SET
                    | MediaPlayerEntityFeature.VOLUME_STEP
                )
                self._attr_volume_level = state.volume / MAX_VOLUME

            if state.mute is None:
                self._attr_is_volume_muted = None
            else:
                features |= MediaPlayerEntityFeature.VOLUME_MUTE
                self._attr_is_volume_muted = state.mute
        else:
            self._attr_source = None
            self._attr_volume_level = None
            self._attr_is_volume_muted = None

        self._attr_supported_features = features

    @catch_command_errors
    async def async_turn_on(self) -> None:
        """Turn the TV on."""
        await self._tv.power_on()

    @catch_command_errors
    async def async_turn_off(self) -> None:
        """Turn the TV off."""
        await self._tv.power_off()

    @catch_command_errors
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._tv.set_volume(round(volume * MAX_VOLUME))

    @catch_command_errors
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the TV."""
        await self._tv.set_mute(mute)

    @catch_command_errors
    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        await self._tv.select_input_source(INPUT_SOURCE_HA_TO_SAMSUNG[source])
