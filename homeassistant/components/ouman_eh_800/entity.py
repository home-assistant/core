"""Base entity for Ouman EH-800."""

from dataclasses import dataclass

from ouman_eh_800_api import OumanEndpoint

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import OumanDevice
from .coordinator import OumanEh800Coordinator


@dataclass(frozen=True, kw_only=True)
class OumanEh800EntityDescription(EntityDescription):
    """Common Ouman EH-800 entity description fields."""

    device: OumanDevice


class OumanEh800Entity(CoordinatorEntity[OumanEh800Coordinator]):
    """Base entity for Ouman EH-800."""

    _attr_has_entity_name = True
    entity_description: OumanEh800EntityDescription

    def __init__(
        self,
        coordinator: OumanEh800Coordinator,
        endpoint: OumanEndpoint,
        description: OumanEh800EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._endpoint = endpoint
        self.entity_description = description

        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}"
            f"_{description.device}_{description.key}"
        )
        self._attr_device_info = coordinator.device_info[description.device]
