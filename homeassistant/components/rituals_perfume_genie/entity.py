"""Base class for Rituals Perfume Genie diffuser entity."""
from __future__ import annotations

from typing import Any

from pyrituals import Diffuser

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTES, BATTERY, DOMAIN, HUB, HUBLOT, SENSORS

MANUFACTURER = "Rituals Cosmetics"
MODEL = "The Perfume Genie"
MODEL2 = "The Perfume Genie 2.0"

ROOMNAME = "roomnamec"
STATUS = "status"
VERSION = "versionc"

AVAILABLE_STATE = 1


class DiffuserEntity(CoordinatorEntity):
    """Representation of a diffuser entity."""

    def __init__(
        self, diffuser: Diffuser, coordinator: CoordinatorEntity, entity_suffix: str
    ) -> None:
        """Init from config, hookup diffuser and coordinator."""
        super().__init__(coordinator)
        self._diffuser = diffuser
        self._entity_suffix = entity_suffix
        self._hublot = self.coordinator.data[HUB][HUBLOT]
        self._hubname = self.coordinator.data[HUB][ATTRIBUTES][ROOMNAME]

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity."""
        return f"{self._hublot}{self._entity_suffix}"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self._hubname}{self._entity_suffix}"

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            super().available and self.coordinator.data[HUB][STATUS] == AVAILABLE_STATE
        )

    @property
    def device_info(self) -> dict[str, Any]:
        """Return information about the device."""
        return {
            "name": self._hubname,
            "identifiers": {(DOMAIN, self._hublot)},
            "manufacturer": MANUFACTURER,
            "model": MODEL if BATTERY in self._diffuser.data[HUB][SENSORS] else MODEL2,
            "sw_version": self.coordinator.data[HUB][SENSORS][VERSION],
        }
