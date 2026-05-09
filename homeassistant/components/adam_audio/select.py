"""Select platform for ADAM Audio — Input Source and Voicing.

Each physical speaker exposes two selects; one 'All Speakers' group select
for each is created once.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity

from .const import (
    DOMAIN,
    ENTITY_INPUT,
    ENTITY_VOICING,
    GROUP_DEVICE_ID,
    INPUT_FROM_INT,
    INPUT_OPTIONS,
    INPUT_TO_INT,
    VOICING_FROM_INT,
    VOICING_OPTIONS,
    VOICING_TO_INT,
)
from .coordinator import AdamAudioCoordinator
from .entity import AdamAudioEntity, AdamAudioGroupEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .data import AdamAudioConfigEntry, AdamAudioIntegrationData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdamAudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator = entry.runtime_data.coordinator
    integration_data: AdamAudioIntegrationData = hass.data[DOMAIN]

    entities: list[SelectEntity] = [
        AdamAudioVoicingSelect(coordinator),
        AdamAudioInputSelect(coordinator),
    ]

    if not integration_data.group_selects_added:
        integration_data.group_selects_added = True
        entities += [
            AdamAudioGroupVoicingSelect(hass),
            AdamAudioGroupInputSelect(hass),
        ]

    async_add_entities(entities)


# ── Per-device selects ────────────────────────────────────────────────────────


class AdamAudioInputSelect(AdamAudioEntity, SelectEntity):
    """Input source selector for a single speaker (RCA / XLR)."""

    _attr_translation_key = "input_source"
    _attr_icon = "mdi:import"
    _attr_options = INPUT_OPTIONS

    def __init__(self, coordinator: AdamAudioCoordinator) -> None:
        """Initialize the input select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device_unique_id}_{ENTITY_INPUT}"

    @property
    def current_option(self) -> str:
        """Return the current input source."""
        return INPUT_FROM_INT.get(self.coordinator.client.state.input_source, "XLR")

    async def async_select_option(self, option: str) -> None:
        """Set the input source."""
        await self.coordinator.client.async_set_input(INPUT_TO_INT[option])
        self.async_write_ha_state()


class AdamAudioVoicingSelect(AdamAudioEntity, SelectEntity):
    """Voicing selector for a single speaker (Pure / UNR / Ext)."""

    _attr_translation_key = "voicing"
    _attr_icon = "mdi:equalizer-outline"
    _attr_options = VOICING_OPTIONS

    def __init__(self, coordinator: AdamAudioCoordinator) -> None:
        """Initialize the voicing select."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.device_unique_id}_{ENTITY_VOICING}"
        )

    @property
    def current_option(self) -> str:
        """Return the current voicing mode."""
        return VOICING_FROM_INT.get(self.coordinator.client.state.voicing, "Pure")

    async def async_select_option(self, option: str) -> None:
        """Set the voicing mode."""
        await self.coordinator.client.async_set_voicing(VOICING_TO_INT[option])
        self.async_write_ha_state()


# ── Group selects ─────────────────────────────────────────────────────────────


class AdamAudioGroupInputSelect(AdamAudioGroupEntity, SelectEntity):
    """Input source selector that controls ALL speakers."""

    _attr_translation_key = "input_source"
    _attr_icon = "mdi:import"
    _attr_options = INPUT_OPTIONS
    _attr_unique_id = f"{DOMAIN}_{GROUP_DEVICE_ID}_{ENTITY_INPUT}"

    @property
    def current_option(self) -> str:
        """Return the common input source, or the first speaker's value."""
        coordinators = self._coordinators()
        if not coordinators:
            return INPUT_OPTIONS[0]
        values = {c.client.state.input_source for c in coordinators}
        raw = (
            next(iter(values))
            if len(values) == 1
            else coordinators[0].client.state.input_source
        )
        return INPUT_FROM_INT.get(raw, "XLR")

    async def async_select_option(self, option: str) -> None:
        """Set the input source on all speakers."""
        value = INPUT_TO_INT[option]
        coordinators = self._coordinators()
        await asyncio.gather(*(c.client.async_set_input(value) for c in coordinators))
        for c in coordinators:
            c.async_set_updated_data(c.client.state)
        self.async_write_ha_state()


class AdamAudioGroupVoicingSelect(AdamAudioGroupEntity, SelectEntity):
    """Voicing selector that controls ALL speakers."""

    _attr_translation_key = "voicing"
    _attr_icon = "mdi:equalizer-outline"
    _attr_options = VOICING_OPTIONS
    _attr_unique_id = f"{DOMAIN}_{GROUP_DEVICE_ID}_{ENTITY_VOICING}"

    @property
    def current_option(self) -> str:
        """Return the common voicing mode, or the first speaker's value."""
        coordinators = self._coordinators()
        if not coordinators:
            return VOICING_OPTIONS[0]
        values = {c.client.state.voicing for c in coordinators}
        raw = (
            next(iter(values))
            if len(values) == 1
            else coordinators[0].client.state.voicing
        )
        return VOICING_FROM_INT.get(raw, "Pure")

    async def async_select_option(self, option: str) -> None:
        """Set the voicing mode on all speakers."""
        value = VOICING_TO_INT[option]
        coordinators = self._coordinators()
        await asyncio.gather(*(c.client.async_set_voicing(value) for c in coordinators))
        for c in coordinators:
            c.async_set_updated_data(c.client.state)
        self.async_write_ha_state()
