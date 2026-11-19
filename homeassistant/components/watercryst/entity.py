"""Common entity definitions."""

from typing import Any, override

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

from .const import DOMAIN
from .coordinator import WatercrystConfigEntry, WatercrystUpdateCoordinator


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
            model=info.get_model_name(),
            model_id=info.device_type_number,
            name=info.name or config_entry.title,
            serial_number=info.biocat_serial,
            sw_version=info.current_firmware_version,
            hw_version=info.current_hardware_version,
            configuration_url=f"https://app.watercryst.com/devices/{info.biocat_serial}",
        )
        self._attr_unique_id = f"{info.biocat_serial}_{entity_description.key}"
        self.entity_description = entity_description

        self.state_coordinator = coordinator.state

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.state_coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @override
    @property
    def available(self) -> bool:
        return (
            super().available
            and self.state_coordinator.last_update_success
            and self.state_coordinator.data.online is True
        )
