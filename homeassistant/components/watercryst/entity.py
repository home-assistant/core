"""Common entity definitions."""

from typing import Any

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import WatercrystConfigEntry
from .const import DOMAIN
from .coordinator import WatercrystUpdateCoordinator


class WatercrystEntity[CoordinatorT: DataUpdateCoordinator[Any]](
    CoordinatorEntity[CoordinatorT]
):
    """WATERCryst coordinator entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: WatercrystConfigEntry,
        coordinator: WatercrystUpdateCoordinator,
        sub_coordinator: CoordinatorT,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize a WatercrystStateEntity instance."""
        super().__init__(sub_coordinator)

        info = coordinator.data

        connections: set[tuple[str, str]] = set()

        if mac := info.system_mac_address:
            connections.add((CONNECTION_NETWORK_MAC, format_mac(mac)))

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.biocat_serial)},
            connections=connections,
            manufacturer="WATERCryst",
            model=info.model,
            model_id=info.device_type_number,
            name=info.name or config_entry.title,
            serial_number=info.biocat_serial,
            sw_version=info.current_firmware_version,
            hw_version=info.current_hardware_version,
            configuration_url=f"https://app.watercryst.com/devices/{info.biocat_serial}",
        )
        self._attr_unique_id = f"{info.biocat_serial}_{entity_description.key}"
        self.entity_description = entity_description
