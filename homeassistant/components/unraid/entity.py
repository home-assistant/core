"""Base entity for Unraid integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import UnraidSystemCoordinator


@dataclass(frozen=True, kw_only=True)
class UnraidEntityDescription(EntityDescription):
    """Base description for all Unraid entities."""


class UnraidSystemEntity(CoordinatorEntity[UnraidSystemCoordinator]):
    """Base class for Unraid system entities."""

    _attr_has_entity_name = True
    entity_description: UnraidEntityDescription

    def __init__(
        self,
        coordinator: UnraidSystemCoordinator,
        entity_description: UnraidEntityDescription,
    ) -> None:
        """Initialize the system entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        server_info = coordinator.server_info
        # UUID must be present as it's validated during config flow
        assert server_info.uuid is not None
        self._attr_unique_id = f"{server_info.uuid}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, server_info.uuid)},
            name=(server_info.hostname or coordinator.config_entry.data[CONF_HOST]),
            manufacturer=server_info.manufacturer or MANUFACTURER,
            model=server_info.model,
            serial_number=server_info.serial_number,
            sw_version=server_info.sw_version,
            hw_version=server_info.hw_version,
            configuration_url=server_info.local_url,
        )
