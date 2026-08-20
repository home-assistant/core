"""Media player platform for Lyngdorf integration."""

from typing import TYPE_CHECKING, override

from lyngdorf.device import Receiver
from lyngdorf.models.base import NumericRange

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import LyngdorfEntity
from .models import LyngdorfConfigEntry

PARALLEL_UPDATES = 1

FEATURES_ZONE_B = (
    MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
)

FEATURES_MAIN = (
    MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.SELECT_SOURCE
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LyngdorfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the receiver from a config entry."""
    runtime_data = config_entry.runtime_data

    entities: list[LyngdorfDevice] = [
        LyngdorfMainDevice(
            runtime_data.receiver, config_entry, runtime_data.device_info
        )
    ]
    if runtime_data.zone_b_device_info is not None:
        entities.append(
            LyngdorfZoneBDevice(
                runtime_data.receiver, config_entry, runtime_data.zone_b_device_info
            )
        )

    async_add_entities(entities)


def _to_ha_volume(volume_db: float, volume_range: NumericRange) -> float:
    """Convert Lyngdorf dB volume to HA 0..1 scale, clamped to 0..1."""
    span = volume_range.max - volume_range.min
    return max(0.0, min((volume_db - volume_range.min) / span, 1.0))


def _to_lyngdorf_volume(volume: float, volume_range: NumericRange) -> float:
    """Convert HA 0..1 volume to Lyngdorf dB scale, clamped to min and max."""
    span = volume_range.max - volume_range.min
    volume_db = volume * span + volume_range.min
    return max(volume_range.min, min(volume_db, volume_range.max))


class LyngdorfDevice(LyngdorfEntity, MediaPlayerEntity):
    """Base Lyngdorf media player entity."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER

    def __init__(
        self,
        receiver: Receiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
        translation_key: str | None,
        entity_id_suffix: str,
        features: MediaPlayerEntityFeature = MediaPlayerEntityFeature(0),
    ) -> None:
        """Initialize the device."""
        super().__init__(receiver, device_info)
        assert config_entry.unique_id
        self._attr_unique_id = f"{config_entry.unique_id}_{entity_id_suffix}"
        self._attr_translation_key = translation_key
        self._attr_supported_features = features


class LyngdorfZoneBDevice(LyngdorfDevice):
    """Lyngdorf Zone B device."""

    def __init__(
        self,
        receiver: Receiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Create the device."""
        super().__init__(
            receiver,
            config_entry,
            device_info,
            None,
            "zone_b",
            FEATURES_ZONE_B,
        )

    @override
    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if self._receiver.zone_b_power_on:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @override
    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean if volume is currently muted."""
        return self._receiver.zone_b_mute_enabled

    @property
    def _volume_range(self) -> NumericRange:
        """Return the model's documented Zone B volume range."""
        volume_range = self._receiver.zone_b_volume_range
        # This entity is only created for models that have a Zone B.
        if TYPE_CHECKING:
            assert volume_range is not None
        return volume_range

    @override
    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if (volume := self._receiver.zone_b_volume) is None:
            return None
        return _to_ha_volume(volume, self._volume_range)

    @override
    async def async_turn_on(self) -> None:
        """Turn on media player."""
        self._receiver.zone_b_power_on = True

    @override
    async def async_turn_off(self) -> None:
        """Turn off media player."""
        self._receiver.zone_b_power_on = False

    @override
    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        self._receiver.zone_b_volume_up()

    @override
    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        self._receiver.zone_b_volume_down()

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._receiver.set_zone_b_volume(
            _to_lyngdorf_volume(volume, self._volume_range)
        )

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self._receiver.zone_b_mute_enabled = mute

    @override
    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._receiver.zone_b_source

    @override
    @property
    def source_list(self) -> list[str] | None:
        """Return the list of available sources."""
        return self._receiver.zone_b_available_sources

    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        self._receiver.zone_b_source = source


class LyngdorfMainDevice(LyngdorfDevice):
    """Lyngdorf main zone device."""

    def __init__(
        self,
        receiver: Receiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Create the device."""
        super().__init__(
            receiver,
            config_entry,
            device_info,
            "main_zone",
            "main_zone",
            FEATURES_MAIN,
        )

    @override
    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if self._receiver.power_on:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @override
    @property
    def source_list(self) -> list[str] | None:
        """Return a list of available input sources."""
        return self._receiver.available_sources

    @override
    @property
    def sound_mode_list(self) -> list[str] | None:
        """Return a list of available sound modes."""
        return self._receiver.available_sound_modes

    @override
    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean if volume is currently muted."""
        return self._receiver.mute_enabled

    @property
    def _volume_range(self) -> NumericRange:
        """Return the model's documented main-zone volume range."""
        volume_range = self._receiver.volume_range
        # Every supported model documents a main-zone volume range.
        if TYPE_CHECKING:
            assert volume_range is not None
        return volume_range

    @override
    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if (volume := self._receiver.volume) is None:
            return None
        return _to_ha_volume(volume, self._volume_range)

    @override
    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._receiver.source

    @override
    @property
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        return self._receiver.sound_mode

    @override
    async def async_turn_on(self) -> None:
        """Turn on media player."""
        self._receiver.power_on = True

    @override
    async def async_turn_off(self) -> None:
        """Turn off media player."""
        self._receiver.power_on = False

    @override
    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        self._receiver.volume_up()

    @override
    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        self._receiver.volume_down()

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._receiver.set_volume(_to_lyngdorf_volume(volume, self._volume_range))

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self._receiver.mute_enabled = mute

    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        self._receiver.sound_mode = sound_mode

    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        self._receiver.source = source
