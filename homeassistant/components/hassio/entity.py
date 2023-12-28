"""Base for Hass.io entities."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, HassioDataUpdateCoordinator
from .const import (
    ATTR_SLUG,
    CONTAINER_STATS,
    CORE_CONTAINER,
    DATA_KEY_ADDONS,
    DATA_KEY_CORE,
    DATA_KEY_HOST,
    DATA_KEY_OS,
    DATA_KEY_SUPERVISOR,
    KEY_TO_UPDATE_TYPES,
    SUPERVISOR_CONTAINER,
)


class HassioAddonEntity(CoordinatorEntity[HassioDataUpdateCoordinator]):
    """Base entity for a Hass.io add-on."""

    _attr_has_entity_name = True

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
        self._attr_unique_id = f"{addon[ATTR_SLUG]}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, addon[ATTR_SLUG])})

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and DATA_KEY_ADDONS in self.coordinator.data
            and self.entity_description.key
            in self.coordinator.data[DATA_KEY_ADDONS].get(self._addon_slug, {})
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        await super().async_added_to_hass()
        update_types = KEY_TO_UPDATE_TYPES[self.entity_description.key]
        self.async_on_remove(
            self.coordinator.async_enable_container_updates(
                self._addon_slug, self.entity_id, update_types
            )
        )
        if CONTAINER_STATS in update_types:
            await self.coordinator.async_request_refresh()


class HassioOSEntity(CoordinatorEntity[HassioDataUpdateCoordinator]):
    """Base Entity for Hass.io OS."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HassioDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"home_assistant_os_{entity_description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "OS")})

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and DATA_KEY_OS in self.coordinator.data
            and self.entity_description.key in self.coordinator.data[DATA_KEY_OS]
        )


class HassioHostEntity(CoordinatorEntity[HassioDataUpdateCoordinator]):
    """Base Entity for Hass.io host."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HassioDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"home_assistant_host_{entity_description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "host")})

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and DATA_KEY_HOST in self.coordinator.data
            and self.entity_description.key in self.coordinator.data[DATA_KEY_HOST]
        )


class HassioSupervisorEntity(CoordinatorEntity[HassioDataUpdateCoordinator]):
    """Base Entity for Supervisor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HassioDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"home_assistant_supervisor_{entity_description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "supervisor")})

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and DATA_KEY_SUPERVISOR in self.coordinator.data
            and self.entity_description.key
            in self.coordinator.data[DATA_KEY_SUPERVISOR]
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        await super().async_added_to_hass()
        update_types = KEY_TO_UPDATE_TYPES[self.entity_description.key]
        self.async_on_remove(
            self.coordinator.async_enable_container_updates(
                SUPERVISOR_CONTAINER, self.entity_id, update_types
            )
        )
        if CONTAINER_STATS in update_types:
            await self.coordinator.async_request_refresh()


class HassioCoreEntity(CoordinatorEntity[HassioDataUpdateCoordinator]):
    """Base Entity for Core."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HassioDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"home_assistant_core_{entity_description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "core")})

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and DATA_KEY_CORE in self.coordinator.data
            and self.entity_description.key in self.coordinator.data[DATA_KEY_CORE]
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        await super().async_added_to_hass()
        update_types = KEY_TO_UPDATE_TYPES[self.entity_description.key]
        self.async_on_remove(
            self.coordinator.async_enable_container_updates(
                CORE_CONTAINER, self.entity_id, update_types
            )
        )
        if CONTAINER_STATS in update_types:
            await self.coordinator.async_request_refresh()
