"""Base class for Rituals Perfume Genie diffuser entity."""
from __future__ import annotations

from pyrituals import Diffuser

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RitualsDataUpdateCoordinator
from .const import DOMAIN

MANUFACTURER = "Rituals Cosmetics"
MODEL = "The Perfume Genie"
MODEL2 = "The Perfume Genie 2.0"


class DiffuserEntity(CoordinatorEntity[RitualsDataUpdateCoordinator]):
    """Representation of a diffuser entity."""

    def __init__(
        self,
        diffuser: Diffuser,
        coordinator: RitualsDataUpdateCoordinator,
        entity_suffix: str,
    ) -> None:
        """Init from config, hookup diffuser and coordinator."""
        super().__init__(coordinator)
        self._diffuser = diffuser

        hublot = self._diffuser.hublot
        hubname = self._diffuser.name

        self._attr_name = f"{hubname}{entity_suffix}"
        self._attr_unique_id = f"{hublot}{entity_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hublot)},
            manufacturer=MANUFACTURER,
            model=MODEL if diffuser.has_battery else MODEL2,
            name=hubname,
            sw_version=diffuser.version,
        )

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self._diffuser.is_online
