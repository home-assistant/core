"""Media player platform for the Sony TV RS-232 integration.

Sony's consumer RS-232 protocol is set-only: the TV acknowledges commands but
does not report changes made with the IR remote, and most models ignore query
packets. The entity is therefore an assumed-state media player: state tracks
acknowledged commands, and query replies on the Pro Bravia displays that
answer them.
"""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, override

from sony_tv_rs232 import (
    InputSource,
    PowerState,
    SerialKitError,
    SonyCommandError,
    SoundMode,
)

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SonyTVCoordinator, SonyTVRS232ConfigEntry

# The library serialises commands on the wire already; 1 keeps HA from queueing
# a burst of service calls behind that lock until they time out.
PARALLEL_UPDATES = 1

INPUT_SOURCE_SONY_TO_HA: dict[InputSource, str] = {
    InputSource.TV: "tv",
    InputSource.VIDEO1: "video1",
    InputSource.VIDEO2: "video2",
    InputSource.VIDEO3: "video3",
    InputSource.COMPONENT1: "component1",
    InputSource.COMPONENT2: "component2",
    InputSource.HDMI1: "hdmi1",
    InputSource.HDMI2: "hdmi2",
    InputSource.HDMI3: "hdmi3",
    InputSource.HDMI4: "hdmi4",
    InputSource.PC: "pc",
}
INPUT_SOURCE_HA_TO_SONY: dict[str, InputSource] = {
    value: key for key, value in INPUT_SOURCE_SONY_TO_HA.items()
}

SOUND_MODE_SONY_TO_HA: dict[SoundMode, str] = {
    SoundMode.DYNAMIC: "dynamic",
    SoundMode.STANDARD: "standard",
    SoundMode.CUSTOM: "custom",
}
SOUND_MODE_HA_TO_SONY: dict[str, SoundMode] = {
    value: key for key, value in SOUND_MODE_SONY_TO_HA.items()
}


def catch_command_errors[**_P](
    func: Callable[_P, Coroutine[Any, Any, None]],
) -> Callable[_P, Coroutine[Any, Any, None]]:
    """Translate library errors raised by an action into HomeAssistantError."""

    @wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(*args, **kwargs)
        except SonyCommandError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={"error": str(err)},
            ) from err
        except (SerialKitError, OSError) as err:
            # SerialKitError covers CommandTimeoutError, ConnectionLostError
            # and the ProtocolError family.
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    return wrapper


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonyTVRS232ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the media player entity for the TV."""
    async_add_entities([SonyTVRS232MediaPlayer(entry.runtime_data)])


class SonyTVRS232MediaPlayer(CoordinatorEntity[SonyTVCoordinator], MediaPlayerEntity):
    """A Sony Bravia TV controlled over RS-232."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "tv"
    _attr_assumed_state = True
    _attr_source_list = list(INPUT_SOURCE_SONY_TO_HA.values())
    _attr_sound_mode_list = list(SOUND_MODE_SONY_TO_HA.values())
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )

    def __init__(self, coordinator: SonyTVCoordinator) -> None:
        """Set up the unique id and device."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer=MANUFACTURER,
        )

    @property
    @override
    def state(self) -> MediaPlayerState | None:
        """Return on/off from the last known power state."""
        power = self.coordinator.data.power
        if power is None:
            return None
        return MediaPlayerState.ON if power is PowerState.ON else MediaPlayerState.OFF

    @property
    @override
    def volume_level(self) -> float | None:
        """Map the TV's 0-100 volume onto 0..1."""
        volume = self.coordinator.data.volume
        return volume / 100 if volume is not None else None

    @property
    @override
    def is_volume_muted(self) -> bool | None:
        """Return the last known mute state."""
        return self.coordinator.data.audio_mute

    @property
    @override
    def source(self) -> str | None:
        """Return the last known input source."""
        current = self.coordinator.data.input_source
        return INPUT_SOURCE_SONY_TO_HA.get(current) if current is not None else None

    @property
    @override
    def sound_mode(self) -> str | None:
        """Return the last known sound mode."""
        mode = self.coordinator.data.sound_mode
        return SOUND_MODE_SONY_TO_HA.get(mode) if mode is not None else None

    @catch_command_errors
    @override
    async def async_turn_on(self) -> None:
        """Turn the TV on (standby listening is armed on every connect)."""
        await self.coordinator.tv.power_on()

    @catch_command_errors
    @override
    async def async_turn_off(self) -> None:
        """Turn the TV off (standby)."""
        await self.coordinator.tv.power_off()

    @catch_command_errors
    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.coordinator.tv.set_volume(round(volume * 100))

    @catch_command_errors
    @override
    async def async_volume_up(self) -> None:
        """Step the volume up."""
        await self.coordinator.tv.volume_up()

    @catch_command_errors
    @override
    async def async_volume_down(self) -> None:
        """Step the volume down."""
        await self.coordinator.tv.volume_down()

    @catch_command_errors
    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the TV."""
        if mute:
            await self.coordinator.tv.mute_on()
        else:
            await self.coordinator.tv.mute_off()

    @catch_command_errors
    @override
    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        await self.coordinator.tv.select_input_source(INPUT_SOURCE_HA_TO_SONY[source])

    @catch_command_errors
    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select a sound mode."""
        await self.coordinator.tv.set_sound_mode(SOUND_MODE_HA_TO_SONY[sound_mode])
