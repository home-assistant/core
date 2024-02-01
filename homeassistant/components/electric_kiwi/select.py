"""Support for Electric Kiwi hour of free power."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, HOP_COORDINATOR
from .coordinator import ElectricKiwiHOPDataCoordinator

_LOGGER = logging.getLogger(__name__)
ATTR_EK_HOP_SELECT = "hop_select"

HOP_SELECT = SelectEntityDescription(
    entity_category=EntityCategory.CONFIG,
    key=ATTR_EK_HOP_SELECT,
    translation_key="hop_selector",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Electric Kiwi select setup."""
    hop_coordinator: ElectricKiwiHOPDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        HOP_COORDINATOR
    ]

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
            f"{coordinator._ek_api.customer_number}"
            f"_{coordinator._ek_api.connection_id}_{description.key}"
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
