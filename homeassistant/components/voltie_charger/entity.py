"""Base entity for the Voltie Charger integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import VoltieChargerConfigEntry, VoltieDataUpdateCoordinator


class VoltieChargerEntity(CoordinatorEntity[VoltieDataUpdateCoordinator]):
    """Defines a Voltie charger entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: VoltieChargerConfigEntry,
        coordinator: VoltieDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        charger_id = entry.runtime_data.data_coordinator.data.status.charger_id
        self._attr_unique_id = f"{charger_id}_{description.key}"
        charger = entry.runtime_data.charger
        status = entry.runtime_data.data_coordinator.data.status
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, charger_id)},
            configuration_url=str(charger.url),
            manufacturer=MANUFACTURER,
            name=entry.title,
            serial_number=charger_id,
            sw_version=status.software_version_string,
        )
