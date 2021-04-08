"""Base for Hass.io entities."""
from __future__ import annotations

from typing import Any

from homeassistant.const import ATTR_NAME
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, HassioDataUpdateCoordinator
from .const import ATTR_SLUG


class HassioAddonEntity(CoordinatorEntity):
    """Base entity for a Hass.io add-on."""

    def __init__(
        self,
        coordinator: HassioDataUpdateCoordinator,
        addon: dict[str, Any],
        attribute_name: str,
        sensor_name: str,
    ) -> None:
        """Initialize base entity."""
        self.addon_slug = addon[ATTR_SLUG]
        self.addon_name = addon[ATTR_NAME]
        self._data_key = "addons"
        self.attribute_name = attribute_name
        self.sensor_name = sensor_name
        super().__init__(coordinator)

    @property
    def addon_info(self) -> dict[str, Any]:
        """Return add-on info."""
        return self.coordinator.data[self._data_key][self.addon_slug]

    @property
    def name(self) -> str:
        """Return entity name."""
        return f"{self.addon_name}: {self.sensor_name}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def unique_id(self) -> str:
        """Return unique ID for entity."""
        return f"{self.addon_slug}_{self.attribute_name}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device specific attributes."""
        return {"identifiers": {(DOMAIN, self.addon_slug)}}


class HassioOSEntity(CoordinatorEntity):
    """Base Entity for Hass.io OS."""

    def __init__(
        self,
        coordinator: HassioDataUpdateCoordinator,
        attribute_name: str,
        sensor_name: str,
    ) -> None:
        """Initialize base entity."""
        self._data_key = "os"
        self.attribute_name = attribute_name
        self.sensor_name = sensor_name
        super().__init__(coordinator)

    @property
    def os_info(self) -> dict[str, Any]:
        """Return OS info."""
        return self.coordinator.data[self._data_key]

    @property
    def name(self) -> str:
        """Return entity name."""
        return f"Home Assistant Operating System: {self.sensor_name}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def unique_id(self) -> str:
        """Return unique ID for entity."""
        return f"home_assistant_os_{self.attribute_name}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device specific attributes."""
        return {"identifiers": {(DOMAIN, "OS")}}
