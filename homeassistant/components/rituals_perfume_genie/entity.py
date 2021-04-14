"""Base class for Rituals Perfume Genie diffuser entity."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTES, DOMAIN, HUB, HUBLOT, SENSORS

MANUFACTURER = "Rituals Cosmetics"
MODEL = "Diffuser"

ROOMNAME = "roomnamec"
VERSION = "versionc"


class DiffuserEntity(CoordinatorEntity):
    """Representation of a diffuser entity."""

    def __init__(self, diffuser, coordinator, entity_suffix):
        """Init from config, hookup diffuser and coordinator."""
        super().__init__(coordinator)
        self._diffuser = diffuser
        self._entity_suffix = entity_suffix
        self._hublot = self.coordinator.data[HUB][HUBLOT]
        self._hubname = self.coordinator.data[HUB][ATTRIBUTES][ROOMNAME]

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self._hublot}{self._entity_suffix}"

    @property
    def name(self):
        """Return the name of the entity."""
        return f"{self._hubname}{self._entity_suffix}"

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "name": self._hubname,
            "identifiers": {(DOMAIN, self._hublot)},
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data[HUB][SENSORS][VERSION],
        }
