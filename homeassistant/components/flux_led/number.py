"""Support for LED numbers."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Coroutine
import logging
from typing import Any, cast

from flux_led.protocol import (
    MUSIC_PIXELS_MAX,
    MUSIC_PIXELS_PER_SEGMENT_MAX,
    MUSIC_SEGMENTS_MAX,
    PIXELS_MAX,
    PIXELS_PER_SEGMENT_MAX,
    SEGMENTS_MAX,
)

from homeassistant import config_entries
from homeassistant.components.light import EFFECT_RANDOM
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FluxLedUpdateCoordinator
from .entity import FluxEntity
from .util import _effect_brightness

_LOGGER = logging.getLogger(__name__)

DEBOUNCE_TIME = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flux lights."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device
    entities: list[
        FluxSpeedNumber
        | FluxPixelsPerSegmentNumber
        | FluxSegmentsNumber
        | FluxMusicPixelsPerSegmentNumber
        | FluxMusicSegmentsNumber
    ] = []
    name = entry.data.get(CONF_NAME, entry.title)
    base_unique_id = entry.unique_id or entry.entry_id

    if device.pixels_per_segment is not None:
        entities.append(
            FluxPixelsPerSegmentNumber(
                coordinator,
                base_unique_id,
                f"{name} Pixels Per Segment",
                "pixels_per_segment",
            )
        )
    if device.segments is not None:
        entities.append(
            FluxSegmentsNumber(
                coordinator, base_unique_id, f"{name} Segments", "segments"
            )
        )
    if device.music_pixels_per_segment is not None:
        entities.append(
            FluxMusicPixelsPerSegmentNumber(
                coordinator,
                base_unique_id,
                f"{name} Music Pixels Per Segment",
                "music_pixels_per_segment",
            )
        )
    if device.music_segments is not None:
        entities.append(
            FluxMusicSegmentsNumber(
                coordinator, base_unique_id, f"{name} Music Segments", "music_segments"
            )
        )
    if device.effect_list and device.effect_list != [EFFECT_RANDOM]:
        entities.append(
            FluxSpeedNumber(coordinator, base_unique_id, f"{name} Effect Speed", None)
        )

    async_add_entities(entities)


class FluxSpeedNumber(
    FluxEntity, CoordinatorEntity[FluxLedUpdateCoordinator], NumberEntity
):
    """Defines a flux_led speed number."""

    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:speedometer"

    @property
    def native_value(self) -> float:
        """Return the effect speed."""
        return cast(float, self._device.speed)

    async def async_set_native_value(self, value: float) -> None:
        """Set the flux speed value."""
        current_effect = self._device.effect
        new_speed = int(value)
        if not current_effect:
            raise HomeAssistantError(
                "Speed can only be adjusted when an effect is active"
            )
        if not self._device.speed_adjust_off and not self._device.is_on:
            raise HomeAssistantError("Speed can only be adjusted when the light is on")
        await self._device.async_set_effect(
            current_effect, new_speed, _effect_brightness(self._device.brightness)
        )
        await self.coordinator.async_request_refresh()


class FluxConfigNumber(
    FluxEntity, CoordinatorEntity[FluxLedUpdateCoordinator], NumberEntity
):
    """Base class for flux config numbers."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        base_unique_id: str,
        name: str,
        key: str | None,
    ) -> None:
        """Initialize the flux number."""
        super().__init__(coordinator, base_unique_id, name, key)
        self._debouncer: Debouncer[Coroutine[Any, Any, None]] | None = None
        self._pending_value: int | None = None

    async def async_added_to_hass(self) -> None:
        """Set up the debouncer when adding to hass."""
        self._debouncer = Debouncer(
            hass=self.hass,
            logger=_LOGGER,
            cooldown=DEBOUNCE_TIME,
            immediate=False,
            function=self._async_set_native_value,
        )
        await super().async_added_to_hass()

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        self._pending_value = int(value)
        assert self._debouncer is not None
        await self._debouncer.async_call()

    @abstractmethod
    async def _async_set_native_value(self) -> None:
        """Call on debounce to set the value."""

    def _pixels_and_segments_fit_in_music_mode(self) -> bool:
        """Check if the base pixel and segment settings will fit for music mode.

        If they fit, they do not need to be configured.
        """
        pixels_per_segment = self._device.pixels_per_segment
        segments = self._device.segments
        assert pixels_per_segment is not None
        assert segments is not None
        return bool(
            pixels_per_segment <= MUSIC_PIXELS_PER_SEGMENT_MAX
            and segments <= MUSIC_SEGMENTS_MAX
            and pixels_per_segment * segments <= MUSIC_PIXELS_MAX
        )


class FluxPixelsPerSegmentNumber(FluxConfigNumber):
    """Defines a flux_led pixels per segment number."""

    _attr_icon = "mdi:dots-grid"

    @property
    def native_max_value(self) -> int:
        """Return the max value."""
        return min(
            PIXELS_PER_SEGMENT_MAX, int(PIXELS_MAX / (self._device.segments or 1))
        )

    @property
    def native_value(self) -> int:
        """Return the pixels per segment."""
        assert self._device.pixels_per_segment is not None
        return self._device.pixels_per_segment

    async def _async_set_native_value(self) -> None:
        """Set the pixels per segment."""
        assert self._pending_value is not None
        await self._device.async_set_device_config(
            pixels_per_segment=self._pending_value
        )


class FluxSegmentsNumber(FluxConfigNumber):
    """Defines a flux_led segments number."""

    _attr_icon = "mdi:segment"

    @property
    def native_max_value(self) -> int:
        """Return the max value."""
        assert self._device.pixels_per_segment is not None
        return min(
            SEGMENTS_MAX, int(PIXELS_MAX / (self._device.pixels_per_segment or 1))
        )

    @property
    def native_value(self) -> int:
        """Return the segments."""
        assert self._device.segments is not None
        return self._device.segments

    async def _async_set_native_value(self) -> None:
        """Set the segments."""
        assert self._pending_value is not None
        await self._device.async_set_device_config(segments=self._pending_value)


class FluxMusicNumber(FluxConfigNumber):
    """A number that is only available if the base pixels do not fit in music mode."""

    @property
    def available(self) -> bool:
        """Return if music pixels per segment can be set."""
        return super().available and not self._pixels_and_segments_fit_in_music_mode()


class FluxMusicPixelsPerSegmentNumber(FluxMusicNumber):
    """Defines a flux_led music pixels per segment number."""

    _attr_icon = "mdi:dots-grid"

    @property
    def native_max_value(self) -> int:
        """Return the max value."""
        assert self._device.music_segments is not None
        return min(
            MUSIC_PIXELS_PER_SEGMENT_MAX,
            int(MUSIC_PIXELS_MAX / (self._device.music_segments or 1)),
        )

    @property
    def native_value(self) -> int:
        """Return the music pixels per segment."""
        assert self._device.music_pixels_per_segment is not None
        return self._device.music_pixels_per_segment

    async def _async_set_native_value(self) -> None:
        """Set the music pixels per segment."""
        assert self._pending_value is not None
        await self._device.async_set_device_config(
            music_pixels_per_segment=self._pending_value
        )


class FluxMusicSegmentsNumber(FluxMusicNumber):
    """Defines a flux_led music segments number."""

    _attr_icon = "mdi:segment"

    @property
    def native_max_value(self) -> int:
        """Return the max value."""
        assert self._device.pixels_per_segment is not None
        return min(
            MUSIC_SEGMENTS_MAX,
            int(MUSIC_PIXELS_MAX / (self._device.music_pixels_per_segment or 1)),
        )

    @property
    def native_value(self) -> int:
        """Return the music segments."""
        assert self._device.music_segments is not None
        return self._device.music_segments

    async def _async_set_native_value(self) -> None:
        """Set the music segments."""
        assert self._pending_value is not None
        await self._device.async_set_device_config(music_segments=self._pending_value)
