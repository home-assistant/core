"""Base for Hass.io entities."""

from __future__ import annotations

from typing import Any

from aiohasupervisor.models.mounts import CIFSMountResponse, NFSMountResponse

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_SLUG,
    CONTAINER_STATS,
    DATA_KEY_ADDONS,
    DATA_KEY_CORE,
    DATA_KEY_HOST,
    DATA_KEY_MOUNTS,
    DATA_KEY_OS,
    DATA_KEY_SUPERVISOR,
    DOMAIN,
)
from .coordinator import (
    HassioAddOnDataUpdateCoordinator,
    HassioMainDataUpdateCoordinator,
    HassioStatsDataUpdateCoordinator,
)


class HassioStatsEntity(CoordinatorEntity[HassioStatsDataUpdateCoordinator]):
    """Base entity for container stats (CPU, memory)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HassioStatsDataUpdateCoordinator,
        entity_description: EntityDescription,
        *,
        container_id: str,
        data_key: str,
        device_id: str,
        unique_id_prefix: str,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._container_id = container_id
        self._data_key = data_key
        self._attr_unique_id = f"{unique_id_prefix}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self._data_key == DATA_KEY_ADDONS:
            return (
                super().available
                and DATA_KEY_ADDONS in self.coordinator.data
                and self.entity_description.key
                in (
                    self.coordinator.data[DATA_KEY_ADDONS].get(self._container_id) or {}
                )
            )
        return (
            super().available
            and self._data_key in self.coordinator.data
            and self.entity_description.key in self.coordinator.data[self._data_key]
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to stats updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_enable_container_updates(
                self._container_id, self.entity_id, {CONTAINER_STATS}
            )
        )
        # Stats are only fetched for containers with subscribed entities.
        # The first coordinator refresh (before entities exist) has no
        # subscribers, so no stats are fetched. Schedule a debounced
        # refresh so that all stats entities registering during platform
        # setup are batched into a single API call.
        await self.coordinator.async_request_refresh()


class HassioAddonEntity(CoordinatorEntity[HassioAddOnDataUpdateCoordinator]):
    """Base entity for a Hass.io add-on."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HassioAddOnDataUpdateCoordinator,
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
        """Subscribe to addon info updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_enable_addon_info_updates(
                self._addon_slug, self.entity_id
            )
        )


class HassioOSEntity(CoordinatorEntity[HassioMainDataUpdateCoordinator]):
    """Base Entity for Hass.io OS."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HassioMainDataUpdateCoordinator,
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


class HassioHostEntity(CoordinatorEntity[HassioMainDataUpdateCoordinator]):
    """Base Entity for Hass.io host."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HassioMainDataUpdateCoordinator,
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


class HassioSupervisorEntity(CoordinatorEntity[HassioMainDataUpdateCoordinator]):
    """Base Entity for Supervisor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HassioMainDataUpdateCoordinator,
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


class HassioCoreEntity(CoordinatorEntity[HassioMainDataUpdateCoordinator]):
    """Base Entity for Core."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HassioMainDataUpdateCoordinator,
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


class HassioMountEntity(CoordinatorEntity[HassioMainDataUpdateCoordinator]):
    """Base Entity for Mount."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HassioMainDataUpdateCoordinator,
        entity_description: EntityDescription,
        mount: CIFSMountResponse | NFSMountResponse,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"home_assistant_mount_{mount.name}_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"mount_{mount.name}")}
        )
        self._mount = mount

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self._mount.name in self.coordinator.data[DATA_KEY_MOUNTS]
        )
