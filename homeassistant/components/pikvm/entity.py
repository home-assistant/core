"""Base entity for the PiKVM integration."""

from typing import TYPE_CHECKING

from pikvm_aio import format_url

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import PiKVMDataUpdateCoordinator


class PiKVMEntity(CoordinatorEntity[PiKVMDataUpdateCoordinator]):
    """Base entity for PiKVM."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PiKVMDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the PiKVM entity."""
        super().__init__(coordinator)
        serial_number = coordinator.config_entry.unique_id
        if TYPE_CHECKING:
            assert serial_number
        info = coordinator.data
        self.entity_description = description
        self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer=MANUFACTURER,
            model=info.model,
            name=info.name,
            serial_number=serial_number,
            hw_version=info.hw.platform.base or None,
            sw_version=info.kvmd_version,
            configuration_url=format_url(coordinator.config_entry.data[CONF_HOST]),
        )
