"""Base class for Rituals Perfume Genie diffuser entity."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RitualsDataUpdateCoordinator

MANUFACTURER = "Rituals Cosmetics"
MODEL = "The Perfume Genie"
MODEL2 = "The Perfume Genie 2.0"


class DiffuserEntity(CoordinatorEntity[RitualsDataUpdateCoordinator]):
    """Representation of a diffuser entity."""

    def __init__(
        self,
        coordinator: RitualsDataUpdateCoordinator,
        entity_suffix: str,
    ) -> None:
        """Init from config, hookup diffuser and coordinator."""
        super().__init__(coordinator)
        hublot = coordinator.diffuser.hublot
        hubname = coordinator.diffuser.name

        self._attr_name = f"{hubname}{entity_suffix}"
        self._attr_unique_id = f"{hublot}{entity_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hublot)},
            manufacturer=MANUFACTURER,
            model=MODEL if coordinator.diffuser.has_battery else MODEL2,
            name=hubname,
            sw_version=coordinator.diffuser.version,
        )

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.coordinator.diffuser.is_online
