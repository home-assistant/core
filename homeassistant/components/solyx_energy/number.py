"""Number entities for the Solyx Energy Nymo integration."""

from typing import TYPE_CHECKING, override

from homeassistant.components.number import NumberEntity

from .entity import SolyxNymoEntity
from .entity_descriptions import NUMBER_DESCRIPTIONS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SolyxEnergyConfigEntry
    from .coordinator import SolyxEnergyCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: SolyxEnergyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Solyx Energy number entities from a config entry."""
    coordinator: SolyxEnergyCoordinator = entry.runtime_data
    async_add_entities(
        SolyxNumberEntity(coordinator, description)
        for description in NUMBER_DESCRIPTIONS
    )


class SolyxNumberEntity(SolyxNymoEntity, NumberEntity):
    """A single Solyx Energy number entity, writable by the user."""

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value of the number from the coordinator data."""
        return getattr(self.coordinator.data, self.entity_description.key, None)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value and push it to the Solyx cloud platform."""
        await self.coordinator.async_set_attribute(self.entity_description.key, value)
