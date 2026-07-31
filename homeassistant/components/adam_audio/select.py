"""Select platform for ADAM Audio — Input Source and Voicing.

Each physical speaker exposes two selects; one 'All Speakers' group select
for each is created once.
"""

from __future__ import annotations

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
        integration_data.group_owner_entry_id = entry.entry_id
        entities += [
            AdamAudioGroupVoicingSelect(hass),
            AdamAudioGroupInputSelect(hass),
        ]

    async_add_entities(entities)


# ── Per-device selects ────────────────────────────────────────────────────────


class AdamAudioInputSelect(AdamAudioEntity, SelectEntity):
    """Input source selector for a single speaker (RCA / XLR)."""

    _attr_translation_key = "input_source"
    _attr_options = INPUT_OPTIONS

    def __init__(self, coordinator: AdamAudioCoordinator) -> None:
        """Initialize the input select."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.entity_unique_id_base}_{ENTITY_INPUT}"
        )

    @property
    def current_option(self) -> str:
        """Return the current input source."""
        return INPUT_FROM_INT.get(self.coordinator.client.state.input_source, "XLR")

    async def async_select_option(self, option: str) -> None:
        """Set the input source."""
        await self.coordinator.client.async_set_input(INPUT_TO_INT[option])
        self.coordinator.async_notify_state()


class AdamAudioVoicingSelect(AdamAudioEntity, SelectEntity):
    """Voicing selector for a single speaker (Pure / UNR / Ext)."""

    _attr_translation_key = "voicing"
    _attr_options = VOICING_OPTIONS

    def __init__(self, coordinator: AdamAudioCoordinator) -> None:
        """Initialize the voicing select."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.entity_unique_id_base}_{ENTITY_VOICING}"
        )

    @property
    def current_option(self) -> str:
        """Return the current voicing mode."""
        return VOICING_FROM_INT.get(self.coordinator.client.state.voicing, "Pure")

    async def async_select_option(self, option: str) -> None:
        """Set the voicing mode."""
        await self.coordinator.client.async_set_voicing(VOICING_TO_INT[option])
        self.coordinator.async_notify_state()


# ── Group selects ─────────────────────────────────────────────────────────────


class AdamAudioGroupInputSelect(AdamAudioGroupEntity, SelectEntity):
    """Input source selector that controls ALL speakers."""

    _attr_translation_key = "input_source"
    _attr_options = INPUT_OPTIONS
    _attr_unique_id = f"{DOMAIN}_{GROUP_DEVICE_ID}_{ENTITY_INPUT}"

    @property
    def current_option(self) -> str:
        """Return the first speaker's input source (they usually match)."""
        coordinators = self._coordinators()
        if not coordinators:
            return INPUT_OPTIONS[0]
        return INPUT_FROM_INT.get(coordinators[0].client.state.input_source, "XLR")

    async def async_select_option(self, option: str) -> None:
        """Set the input source on all speakers."""
        await self._async_call_all("async_set_input", INPUT_TO_INT[option])


class AdamAudioGroupVoicingSelect(AdamAudioGroupEntity, SelectEntity):
    """Voicing selector that controls ALL speakers."""

    _attr_translation_key = "voicing"
    _attr_options = VOICING_OPTIONS
    _attr_unique_id = f"{DOMAIN}_{GROUP_DEVICE_ID}_{ENTITY_VOICING}"

    @property
    def current_option(self) -> str:
        """Return the first speaker's voicing mode (they usually match)."""
        coordinators = self._coordinators()
        if not coordinators:
            return VOICING_OPTIONS[0]
        return VOICING_FROM_INT.get(coordinators[0].client.state.voicing, "Pure")

    async def async_select_option(self, option: str) -> None:
        """Set the voicing mode on all speakers."""
        await self._async_call_all("async_set_voicing", VOICING_TO_INT[option])
