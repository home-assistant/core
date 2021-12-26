"""Base for Hass.io entities."""
from __future__ import annotations

from typing import Any

from homeassistant.const import ATTR_NAME
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, HassioDataUpdateCoordinator
from .const import ATTR_SLUG, DATA_KEY_ADDONS, DATA_KEY_OS


class HassioAddonEntity(CoordinatorEntity):
    """Base entity for a Hass.io add-on."""

    def __init__(
        self,
        coordinator: HassioDataUpdateCoordinator,
        entity_description: EntityDescription,
        addon: dict[str, Any],
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._addon_slug = addon[ATTR_SLUG]
        self._attr_name = f"{addon[ATTR_NAME]}: {entity_description.name}"
        self._attr_unique_id = f"{addon[ATTR_SLUG]}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, addon[ATTR_SLUG])})

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.entity_description.key
            in self.coordinator.data[DATA_KEY_ADDONS][self._addon_slug]
        )


class HassioOSEntity(CoordinatorEntity):
    """Base Entity for Hass.io OS."""

    def __init__(
        self,
        coordinator: HassioDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_name = f"Home Assistant Operating System: {entity_description.name}"
        self._attr_unique_id = f"home_assistant_os_{entity_description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "OS")})

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.entity_description.key in self.coordinator.data[DATA_KEY_OS]
        )
