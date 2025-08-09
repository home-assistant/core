"""Base entity for Linea Research integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import LineaResearchDataUpdateCoordinator


class LineaResearchEntity(CoordinatorEntity[LineaResearchDataUpdateCoordinator]):
    """Base entity for Linea Research amplifiers."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LineaResearchDataUpdateCoordinator,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        
        device_serial = coordinator.device_info.get(
            "serial", 
            f"{coordinator.config_entry.data['host']}:{coordinator.config_entry.data['port']}"
        )
        
        self._attr_unique_id = f"{device_serial}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_serial)},
            name=f"{NAME} {coordinator.device_info.get('model', 'Amplifier')}",
            manufacturer=MANUFACTURER,
            model=coordinator.device_info.get("model", "Unknown"),
            sw_version=coordinator.device_info.get("firmware", "Unknown"),
        )