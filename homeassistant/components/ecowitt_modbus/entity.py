"""What every Ecowitt Modbus entity shares."""

from dataclasses import dataclass

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import EcowittDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class EcowittEntityDescription(EntityDescription):
    """Which component of the sensor array an entity reads through."""

    component: str  # attribute name on the device, e.g. 'sensors'


class EcowittEntity(CoordinatorEntity[EcowittDataUpdateCoordinator]):
    """An entity backed by one component of an Ecowitt sensor array."""

    _attr_has_entity_name = True
    entity_description: EcowittEntityDescription

    def __init__(
        self,
        coordinator: EcowittDataUpdateCoordinator,
        entity_description: EcowittEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        # The config entry's unique ID is the sensor array's serial number
        # where the model reports one, and its address where it does not;
        # either way it is what the device registry entry is keyed on.
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{entity_description.key}"
        )
        self._attr_device_info = coordinator.device_info
