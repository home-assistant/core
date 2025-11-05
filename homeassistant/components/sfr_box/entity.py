"""SFR Box base entity."""

from __future__ import annotations

from sfrbox_api.models import SystemInfo

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SFRDataUpdateCoordinator


class SFREntity(Entity):
    """SFR Box entity."""

    _attr_has_entity_name = True

    def __init__(self, description: EntityDescription, system_info: SystemInfo) -> None:
        """Initialize the entity."""
        self.entity_description = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_info.mac_addr)},
        )
        self._attr_unique_id = f"{system_info.mac_addr}_{description.key}"


class SFRCoordinatorEntity[_T](
    CoordinatorEntity[SFRDataUpdateCoordinator[_T]], SFREntity
):
    """SFR Box coordinator entity."""

    def __init__(
        self,
        coordinator: SFRDataUpdateCoordinator[_T],
        description: EntityDescription,
        system_info: SystemInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        SFREntity.__init__(self, description, system_info)
        self._attr_unique_id = (
            f"{system_info.mac_addr}_{coordinator.name}_{description.key}"
        )
