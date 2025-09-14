"""Base class for Rituals Perfume Genie diffuser entity."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RitualsDataUpdateCoordinator

MANUFACTURER = "Rituals Cosmetics"
MODEL = "The Perfume Genie"
MODEL2 = "The Perfume Genie 2.0"


def _normalize_fw(v: Any) -> str:
    """Return firmware version as a string from various shapes (str/dict/object)."""
    if not v:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        for key in ("raw", "title", "version", "current", "fw"):
            val = v.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return str(v)
    # object with attributes
    for attr in ("raw", "title", "version", "current", "fw"):
        val = getattr(v, attr, None)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return str(v)


class DiffuserEntity(CoordinatorEntity[RitualsDataUpdateCoordinator]):
    """Representation of a diffuser entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RitualsDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Init from config, hookup diffuser and coordinator."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.diffuser.hublot}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.diffuser.hublot)},
            manufacturer=MANUFACTURER,
            model=MODEL if coordinator.diffuser.has_battery else MODEL2,
            name=coordinator.diffuser.name or "Rituals Perfume Genie",
            sw_version=_normalize_fw(getattr(coordinator.diffuser, "version", None)),
        )

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.coordinator.diffuser.is_online
