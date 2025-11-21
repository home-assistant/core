"""Base entity for Essent integration."""
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import EssentDataUpdateCoordinator


class EssentEntity(CoordinatorEntity[EssentDataUpdateCoordinator]):
    """Base class for Essent entities."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: EssentDataUpdateCoordinator,
        energy_type: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.energy_type = energy_type
        entry_identifier = (
            coordinator.config_entry.entry_id
            if coordinator.config_entry is not None
            else "essent_dynamic_prices"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_identifier)},
            name="Essent",
            manufacturer="Essent",
        )
