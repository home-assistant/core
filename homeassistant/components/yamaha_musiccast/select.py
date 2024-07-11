"""The select entities for musiccast."""

from __future__ import annotations

from aiomusiccast.capabilities import OptionSetter

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, MusicCastCapabilityEntity, MusicCastDataUpdateCoordinator
from .const import TRANSLATION_KEY_MAPPING


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MusicCast select entities based on a config entry."""
    coordinator: MusicCastDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    select_entities = [
        SelectableCapability(coordinator, capability)
        for capability in coordinator.data.capabilities
        if isinstance(capability, OptionSetter)
    ]

    select_entities.extend(
        SelectableCapability(coordinator, capability, zone)
        for zone, data in coordinator.data.zones.items()
        for capability in data.capabilities
        if isinstance(capability, OptionSetter)
    )

    async_add_entities(select_entities)


class SelectableCapability(MusicCastCapabilityEntity, SelectEntity):
    """Representation of a MusicCast Select entity."""

    capability: OptionSetter

    def __init__(
        self,
        coordinator: MusicCastDataUpdateCoordinator,
        capability: OptionSetter,
        zone_id: str | None = None,
    ) -> None:
        """Initialize the MusicCast Select entity."""
        MusicCastCapabilityEntity.__init__(self, coordinator, capability, zone_id)
        self._attr_options = list(capability.options.values())
        self._attr_translation_key = TRANSLATION_KEY_MAPPING.get(capability.id)

    async def async_select_option(self, option: str) -> None:
        """Select the given option."""
        value = {val: key for key, val in self.capability.options.items()}[option]
        await self.capability.set(value)
        self._attr_translation_key = TRANSLATION_KEY_MAPPING.get(self.capability.id)

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        return self.capability.options.get(self.capability.current)
