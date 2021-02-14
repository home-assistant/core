"""Base for Hass.io entities."""
import re
from typing import Any, Dict

from homeassistant.const import ATTR_SERVICE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import DOMAIN, HassioAddonsDataUpdateCoordinator
from .const import ATTR_NAME, ATTR_SLUG, ATTR_URL, ATTR_VERSION


class HassioAddonEntity(CoordinatorEntity):
    """Binary sensor to track whether an update is available for a Hass.io add-on."""

    def __init__(
        self,
        coordinator: HassioAddonsDataUpdateCoordinator,
        addon: Dict[str, Any],
        sensor_name: str,
    ) -> None:
        """Initialize binary sensor."""
        self.addon_slug = addon[ATTR_SLUG]
        self.addon_name = addon[ATTR_NAME]
        try:
            # Get github username or organization
            self.user_or_org = re.sub("^https?://", "", addon[ATTR_URL]).split("/")[1]
        except IndexError:
            # fall back on unknown in case of Exception
            self.user_or_org = "unknown"
        self.sensor_name = sensor_name
        super().__init__(coordinator)

    @property
    def addon_info(self) -> Dict[str, Any]:
        """Return add-on info."""
        return self.coordinator.data[self.addon_slug]

    @property
    def name(self) -> str:
        """Return entity name."""
        return f"{self.addon_name} Hass.io Add-on: {self.sensor_name.replace('_', ' ').title()}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def unique_id(self) -> str:
        """Return unique ID for entity."""
        return f"{self.addon_slug}_{slugify(self.sensor_name)}"

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device specific attributes."""
        return {
            "name": self.addon_name,
            "identifiers": {(DOMAIN, self.addon_slug)},
            "manufacturer": self.user_or_org,
            "model": "Hass.io Add-On",
            "sw_version": self.addon_info[ATTR_VERSION],
            "entry_type": ATTR_SERVICE,
        }
