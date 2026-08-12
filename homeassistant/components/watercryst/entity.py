"""Abstract entity definitions."""

from typing import Any

from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WatercrystConfigEntry
from .coordinator import WatercrystDataUpdateCoordinator


class WatercrystEntity[CoordinatorT: WatercrystDataUpdateCoordinator[Any]](
    CoordinatorEntity[CoordinatorT], Entity
):
    """An abstract class for WATERCryst entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: WatercrystConfigEntry,
        coordinator: CoordinatorT,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize a WatercrystEntity instance."""
        Entity.__init__(self)
        CoordinatorEntity.__init__(self, coordinator)

        data = config_entry.runtime_data

        self._attr_device_info = data.device_info
        self._attr_unique_id = f"{data.biocat_serial_number}_{entity_description.key}"

        self.entity_description = entity_description
        self.runtime_data = data

        self._client = config_entry.runtime_data.client
