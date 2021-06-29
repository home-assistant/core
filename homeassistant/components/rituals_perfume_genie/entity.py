"""Base class for Rituals Perfume Genie diffuser entity."""
from __future__ import annotations

from pyrituals import Diffuser

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RitualsDataUpdateCoordinator
from .const import DOMAIN, HUBLOT, SENSORS

MANUFACTURER = "Rituals Cosmetics"
MODEL = "The Perfume Genie"
MODEL2 = "The Perfume Genie 2.0"

ATTRIBUTES = "attributes"
ROOMNAME = "roomnamec"
STATUS = "status"
VERSION = "versionc"

AVAILABLE_STATE = 1


class DiffuserEntity(CoordinatorEntity):
    """Representation of a diffuser entity."""

    coordinator: RitualsDataUpdateCoordinator

    def __init__(
        self,
        diffuser: Diffuser,
        coordinator: RitualsDataUpdateCoordinator,
        entity_suffix: str,
    ) -> None:
        """Init from config, hookup diffuser and coordinator."""
        super().__init__(coordinator)
        self._diffuser = diffuser

        hublot = self._diffuser.hub_data[HUBLOT]
        hubname = self._diffuser.hub_data[ATTRIBUTES][ROOMNAME]

        self._attr_name = f"{hubname}{entity_suffix}"
        self._attr_unique_id = f"{hublot}{entity_suffix}"
        self._attr_device_info = {
            "name": hubname,
            "identifiers": {(DOMAIN, hublot)},
            "manufacturer": MANUFACTURER,
            "model": MODEL if diffuser.has_battery else MODEL2,
            "sw_version": diffuser.hub_data[SENSORS][VERSION],
        }

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self._diffuser.hub_data[STATUS] == AVAILABLE_STATE
