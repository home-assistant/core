"""Base entity for Essent integration."""

from essent_dynamic_pricing.models import EnergyData

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, EnergyType
from .coordinator import EssentDataUpdateCoordinator


class EssentEntity(CoordinatorEntity[EssentDataUpdateCoordinator]):
    """Base class for Essent entities."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: EssentDataUpdateCoordinator,
        energy_type: EnergyType,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.energy_type = energy_type
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Essent",
            manufacturer="Essent",
        )

    @property
    def energy_data(self) -> EnergyData:
        """Return the energy data for this entity."""
        return getattr(self.coordinator.data, self.energy_type.value)
