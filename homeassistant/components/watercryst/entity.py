"""Abstract entity definitions."""

from typing import Any, override

from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WatercrystConfigEntry
from .coordinator import WatercrystDataUpdateCoordinator


class WatercrystEntity[CoordinatorT: WatercrystDataUpdateCoordinator[Any]](
    CoordinatorEntity[CoordinatorT], Entity
):
    """An abstract class for WATERCryst entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: WatercrystConfigEntry,
        coordinator: CoordinatorT,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize a WatercrystEntity instance."""
        super().__init__(coordinator)

        data = config_entry.runtime_data

        self._attr_device_info = data.device_info
        self._attr_unique_id = f"{data.biocat_serial_number}_{entity_description.key}"

        self.entity_description = entity_description
        self._state = data.state

    @override
    @property
    def available(self) -> bool:
        """Return whether the device is available."""
        return (
            super().available
            and self._state.data is not None
            and self._state.data.online
        )
