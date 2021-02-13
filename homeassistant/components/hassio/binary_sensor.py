"""Binary sensor platform for Hass.io addons."""
from typing import Any, Callable, Dict, List

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ADDONS_COORDINATOR, DOMAIN, HassioAddonsDataUpdateCoordinator
from .const import (
    ATTR_NAME,
    ATTR_SERVICE,
    ATTR_SLUG,
    ATTR_UPDATE_AVAILABLE,
    ATTR_VERSION,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Binary sensor set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    async_add_entities(
        [
            HassioAddonUpdateAvailableEntity(coordinator, addon)
            for addon in coordinator.data.values()
        ]
    )


class HassioAddonUpdateAvailableEntity(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor to track whether an update is available for a Hass.io add-on."""

    def __init__(
        self, coordinator: HassioAddonsDataUpdateCoordinator, addon: Dict[str, Any]
    ) -> None:
        """Initialize binary sensor."""
        self.addon_slug = addon[ATTR_SLUG]
        self.addon_name = addon[ATTR_NAME]
        super().__init__(coordinator)

    @property
    def addon_info(self) -> Dict[str, Any]:
        """Return add-on info."""
        return self.coordinator.data[self.addon_slug]

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.addon_info[ATTR_UPDATE_AVAILABLE]

    @property
    def name(self) -> str:
        """Return entity name."""
        return f"{self.addon_name} Hass.io Add-on: Update Available"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def unique_id(self) -> str:
        """Return unique ID for entity."""
        return f"{self.addon_slug}_update_available"

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device specific attributes."""
        return {
            "name": self.addon_slug,
            "identifiers": {(DOMAIN, self.addon_slug)},
            "manufacturer": DOMAIN,
            "model": "Add-On",
            "sw_version": self.addon_info[ATTR_VERSION],
            "entry_type": ATTR_SERVICE,
        }
