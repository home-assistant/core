"""Base entity for Coolmaster integration."""

from typing import override

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CoolmasterDataUpdateCoordinator
from .const import DOMAIN


class CoolmasterEntity(CoordinatorEntity[CoolmasterDataUpdateCoordinator]):
    """Representation of a Coolmaster entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CoolmasterDataUpdateCoordinator,
        unit_id: str,
    ) -> None:
        """Initiate CoolmasterEntity."""
        super().__init__(coordinator)
        self._unit_id: str = unit_id
        self._unit = coordinator.data[self._unit_id]
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, unit_id)},
            manufacturer="CoolAutomation",
            model="CoolMasterNet",
            name=unit_id,
            sw_version=coordinator.info["version"],
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self._unit = self.coordinator.data[self._unit_id]
        super()._handle_coordinator_update()


class CoolmasterDescriptionEntity(CoolmasterEntity):
    """A Coolmaster entity described by an entity description."""

    entity_description: EntityDescription

    def __init__(
        self,
        coordinator: CoolmasterDataUpdateCoordinator,
        unit_id: str,
    ) -> None:
        """Initiate CoolmasterDescriptionEntity."""
        super().__init__(coordinator, unit_id)
        self._attr_unique_id = f"{unit_id}-{self.entity_description.key}"
