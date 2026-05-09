"""Number platform for ADAM Audio — EQ controls.

EQ controls (Bass, Desk, Presence, Treble) use integer dB steps.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberMode

from .client import AdamAudioState
from .const import (
    BASS_MAX,
    BASS_MIN,
    DESK_MAX,
    DESK_MIN,
    DOMAIN,
    ENTITY_BASS,
    ENTITY_DESK,
    ENTITY_PRESENCE,
    ENTITY_TREBLE,
    EQ_STEP,
    EQ_UNIT,
    GROUP_DEVICE_ID,
    PRESENCE_MAX,
    PRESENCE_MIN,
    TREBLE_MAX,
    TREBLE_MIN,
)
from .coordinator import AdamAudioCoordinator
from .entity import AdamAudioEntity, AdamAudioGroupEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .data import AdamAudioConfigEntry, AdamAudioIntegrationData


# ── Entity descriptors ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _NumberDesc:
    """Descriptor for a number entity."""

    translation_key: str
    icon: str
    native_min: float
    native_max: float
    native_step: float
    native_unit: str
    state_getter: Callable[[AdamAudioState], float]
    # Async setter signature: async_set_XXX(value)
    setter_name: str
    # Voicing modes where this control is active (None = always available)
    valid_voicings: tuple[int, ...] | None = None


_NUMBER_DESCRIPTORS: tuple[_NumberDesc, ...] = (
    _NumberDesc(
        translation_key=ENTITY_BASS,
        icon="mdi:equalizer",
        native_min=BASS_MIN,
        native_max=BASS_MAX,
        native_step=EQ_STEP,
        native_unit=EQ_UNIT,
        state_getter=lambda s: float(s.bass),
        setter_name="async_set_bass",
        valid_voicings=(0, 1),  # Pure, UNR
    ),
    _NumberDesc(
        translation_key=ENTITY_DESK,
        icon="mdi:tune-vertical",
        native_min=DESK_MIN,
        native_max=DESK_MAX,
        native_step=EQ_STEP,
        native_unit=EQ_UNIT,
        state_getter=lambda s: float(s.desk),
        setter_name="async_set_desk",
        valid_voicings=(0, 1),  # Pure, UNR
    ),
    _NumberDesc(
        translation_key=ENTITY_PRESENCE,
        icon="mdi:tune",
        native_min=PRESENCE_MIN,
        native_max=PRESENCE_MAX,
        native_step=EQ_STEP,
        native_unit=EQ_UNIT,
        state_getter=lambda s: float(s.presence),
        setter_name="async_set_presence",
        valid_voicings=(0, 1),  # Pure, UNR
    ),
    _NumberDesc(
        translation_key=ENTITY_TREBLE,
        icon="mdi:tune-vertical-variant",
        native_min=TREBLE_MIN,
        native_max=TREBLE_MAX,
        native_step=EQ_STEP,
        native_unit=EQ_UNIT,
        state_getter=lambda s: float(s.treble),
        setter_name="async_set_treble",
        valid_voicings=(0, 1),  # Pure, UNR
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdamAudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number platform."""
    coordinator = entry.runtime_data.coordinator
    integration_data: AdamAudioIntegrationData = hass.data[DOMAIN]

    entities: list[NumberEntity] = [
        AdamAudioNumber(coordinator, desc) for desc in _NUMBER_DESCRIPTORS
    ]

    if not integration_data.group_numbers_added:
        integration_data.group_numbers_added = True
        entities += [AdamAudioGroupNumber(hass, desc) for desc in _NUMBER_DESCRIPTORS]

    async_add_entities(entities)


# ── Per-device number ─────────────────────────────────────────────────────────


class AdamAudioNumber(AdamAudioEntity, NumberEntity):
    """Number entity for a single speaker."""

    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: AdamAudioCoordinator, desc: _NumberDesc) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._desc = desc
        self._attr_translation_key = desc.translation_key
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.device_unique_id}_{desc.translation_key}"
        )
        self._attr_icon = desc.icon
        self._attr_native_min_value = desc.native_min
        self._attr_native_max_value = desc.native_max
        self._attr_native_step = desc.native_step
        self._attr_native_unit_of_measurement = desc.native_unit

    @property
    def available(self) -> bool:
        """Return true if the entity is available and the voicing is valid."""
        if not super().available:
            return False
        if self._desc.valid_voicings is not None:
            return self.coordinator.client.state.voicing in self._desc.valid_voicings
        return True

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self._desc.state_getter(self.coordinator.client.state)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value on the device."""
        setter = getattr(self.coordinator.client, self._desc.setter_name)
        # EQ controls expect int
        if self._desc.native_step == 1.0:
            value = int(value)
        await setter(value)
        self.async_write_ha_state()


# ── Group number ──────────────────────────────────────────────────────────────


class AdamAudioGroupNumber(AdamAudioGroupEntity, NumberEntity):
    """Number entity that controls ALL speakers simultaneously."""

    _attr_mode = NumberMode.SLIDER

    def __init__(self, hass: HomeAssistant, desc: _NumberDesc) -> None:
        """Initialize the group number entity."""
        super().__init__(hass)
        self._desc = desc
        self._attr_translation_key = desc.translation_key
        self._attr_unique_id = f"{DOMAIN}_{GROUP_DEVICE_ID}_{desc.translation_key}"
        self._attr_icon = desc.icon
        self._attr_native_min_value = desc.native_min
        self._attr_native_max_value = desc.native_max
        self._attr_native_step = desc.native_step
        self._attr_native_unit_of_measurement = desc.native_unit

    @property
    def available(self) -> bool:
        """Return true if at least one speaker supports the voicing."""
        if not super().available:
            return False
        if self._desc.valid_voicings is not None:
            return any(
                c.client.state.voicing in self._desc.valid_voicings
                for c in self._coordinators()
            )
        return True

    @property
    def native_value(self) -> float:
        """Return the average across all speakers."""
        coordinators = self._coordinators()
        if not coordinators:
            return self._desc.native_min
        values = [self._desc.state_getter(c.client.state) for c in coordinators]
        return round(sum(values) / len(values), 1)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value on all speakers."""
        if self._desc.native_step == 1.0:
            value = int(value)
        coordinators = self._coordinators()
        await asyncio.gather(
            *(getattr(c.client, self._desc.setter_name)(value) for c in coordinators)
        )
        # Push the optimistic state to all per-speaker entities instantly
        for c in coordinators:
            c.async_set_updated_data(c.client.state)
        self.async_write_ha_state()
