"""Base entity for the CatGenie integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from catgenie import Device

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CatGenieCoordinator


@dataclass(frozen=True, kw_only=True)
class CatGenieEntityDescription(EntityDescription):
    """Describe a CatGenie entity."""

    available_fn: Callable[[Device], bool] = lambda _: True


class CatGenieEntity(CoordinatorEntity[CatGenieCoordinator]):
    """Defines a CatGenie entity."""

    _attr_has_entity_name = True
    entity_description: CatGenieEntityDescription

    def __init__(
        self,
        coordinator: CatGenieCoordinator,
        description: CatGenieEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize the CatGenie entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._device_id = device_id
        device = self.device_data
        assert device is not None
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, device.mac_address)},
            identifiers={(DOMAIN, device_id)},
            name=device.name,
            manufacturer="PetNovations",
            model="CatGenie AI",
            sw_version=device.fw_version,
            hw_version=device.hw_revision,
        )

    @property
    def device_data(self) -> Device | None:
        """Return the device data for this entity."""
        return self.coordinator.data.get(self._device_id)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if (device := self.device_data) is None:
            return False
        return (
            super().available
            and device.is_online
            and self.entity_description.available_fn(device)
        )
