"""Base entity for Vizio SmartCast devices."""

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VizioConfigEntry, VizioDeviceCoordinator


class VizioEntity(CoordinatorEntity[VizioDeviceCoordinator]):
    """Base class for Vizio SmartCast entities."""

    _attr_has_entity_name = True

    def __init__(self, config_entry: VizioConfigEntry) -> None:
        """Initialize the Vizio entity."""
        coordinator = config_entry.runtime_data.device_coordinator
        super().__init__(coordinator)
        self._attr_unique_id = unique_id = config_entry.unique_id
        # Guard against config entries missing unique_id, which should never happen
        if TYPE_CHECKING:
            assert unique_id is not None
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})
        self._device = coordinator.device


class VizioDescriptionEntity(VizioEntity):
    """Base class for Vizio entities described by an entity description."""

    def __init__(
        self, config_entry: VizioConfigEntry, description: EntityDescription
    ) -> None:
        """Initialize the Vizio entity from its description."""
        super().__init__(config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{self._attr_unique_id}_{description.key}"
