"""Select entities for the Solyx Energy Nymo integration."""

from typing import TYPE_CHECKING, override

from homeassistant.components.select import SelectEntity

from .entity import SolyxNymoEntity
from .entity_descriptions import SELECT_DESCRIPTIONS, SolyxSelectEntityDescription

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
    """Set up Solyx Energy select entities from a config entry."""
    coordinator: SolyxEnergyCoordinator = entry.runtime_data
    async_add_entities(
        SolyxSelectEntity(coordinator, description)
        for description in SELECT_DESCRIPTIONS
    )


class SolyxSelectEntity(SolyxNymoEntity, SelectEntity):
    """A single Solyx Energy select entity, writable by the user."""

    entity_description: SolyxSelectEntityDescription

    def __init__(
        self,
        coordinator: SolyxEnergyCoordinator,
        description: SolyxSelectEntityDescription,
    ) -> None:
        """Initialize a Solyx Energy select entity with custom description class."""
        super().__init__(coordinator, description)
        self._attr_options = list(description.options_map.values())
        self._values_map = {v: k for k, v in description.options_map.items()}

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option from the coordinator data."""
        raw = getattr(self.coordinator.data, self.entity_description.key, None)
        if raw is None:
            return None
        return self.entity_description.options_map.get(raw)

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option and push it to the Solyx cloud platform."""
        await self.coordinator.async_set_attribute(
            self.entity_description.key, self._values_map[option]
        )
