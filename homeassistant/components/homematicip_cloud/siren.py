"""Support for HomematicIP Cloud sirens."""

from __future__ import annotations

import logging
from typing import Any

from homematicip.base.functionalChannels import NotificationMp3SoundChannel
from homematicip.device import CombinationSignallingDevice

from homeassistant.components.siren import (
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP

_logger = logging.getLogger(__name__)

# Map tone integers to HmIP sound file strings
_TONE_TO_SOUNDFILE: dict[int, str] = {0: "INTERNAL_SOUNDFILE"}
_TONE_TO_SOUNDFILE.update({i: f"SOUNDFILE_{i:03d}" for i in range(1, 253)})

# Available tones as dict[int, str] for HA UI
AVAILABLE_TONES: dict[int, str] = {0: "Internal"}
AVAILABLE_TONES.update({i: f"Sound {i}" for i in range(1, 253)})


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP Cloud sirens from a config entry."""
    hap = config_entry.runtime_data
    async_add_entities(
        HomematicipMP3Siren(hap, device)
        for device in hap.home.devices
        if isinstance(device, CombinationSignallingDevice)
    )


class HomematicipMP3Siren(HomematicipGenericEntity, SirenEntity):
    """Representation of the HomematicIP MP3 siren (HmIP-MP3P)."""

    _attr_available_tones = AVAILABLE_TONES
    _attr_supported_features = (
        SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.TONES
        | SirenEntityFeature.VOLUME_SET
    )

    def __init__(
        self, hap: HomematicipHAP, device: CombinationSignallingDevice
    ) -> None:
        """Initialize the siren entity."""
        super().__init__(hap, device, post="Siren", channel=1, is_multi_channel=False)

    @property
    def _func_channel(self) -> NotificationMp3SoundChannel:
        return self._device.functionalChannels[self._channel]

    @property
    def is_on(self) -> bool:
        """Return true if siren is playing."""
        return self._func_channel.playingFileActive

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on."""
        tone = kwargs.get(ATTR_TONE, 0)
        volume_level = kwargs.get(ATTR_VOLUME_LEVEL, 1.0)

        sound_file = _TONE_TO_SOUNDFILE.get(tone, "INTERNAL_SOUNDFILE")
        await self._func_channel.set_sound_file_volume_level_async(
            sound_file=sound_file, volume_level=volume_level
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        await self._func_channel.stop_sound_async()
