"""Support for Electric Kiwi hour of free power."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION
from .coordinator import ElectricKiwiConfigEntry, ElectricKiwiHOPDataCoordinator

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)
ATTR_EK_HOP_SELECT = "hop_select"

HOP_SELECT = SelectEntityDescription(
    entity_category=EntityCategory.CONFIG,
    key=ATTR_EK_HOP_SELECT,
    translation_key="hop_selector",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectricKiwiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Electric Kiwi select setup."""
    hop_coordinator = entry.runtime_data.hop

    _LOGGER.debug("Setting up select entity")
    async_add_entities([ElectricKiwiSelectHOPEntity(hop_coordinator, HOP_SELECT)])


class ElectricKiwiSelectHOPEntity(
    CoordinatorEntity[ElectricKiwiHOPDataCoordinator], SelectEntity
):
    """Entity object for seeing and setting the hour of free power."""

    entity_description: SelectEntityDescription
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    values_dict: dict[str, int]

    def __init__(
        self,
        coordinator: ElectricKiwiHOPDataCoordinator,
        description: SelectEntityDescription,
    ) -> None:
        """Initialise the HOP selection entity."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.ek_api.customer_number}"
            f"_{coordinator.ek_api.electricity.identifier}_{description.key}"
        )
        self.entity_description = description
        self.values_dict = coordinator.get_hop_options()
        self._attr_options = list(self.values_dict)

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        return (
            f"{self.coordinator.data.start.start_time}"
            f" - {self.coordinator.data.end.end_time}"
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        value = self.values_dict[option]
        await self.coordinator.async_update_hop(value)
        self.async_write_ha_state()
