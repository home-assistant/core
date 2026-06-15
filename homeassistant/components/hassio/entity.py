"""Base for Hass.io entities."""

from collections.abc import Callable

from aiohasupervisor.models import CIFSMountResponse, HostInfo, NFSMountResponse, OSInfo
from aiohasupervisor.models.base import ContainerStats

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONTAINER_STATS, DOMAIN
from .coordinator import (
    AddonData,
    HassioAddOnDataUpdateCoordinator,
    HassioMainDataUpdateCoordinator,
    HassioStatsData,
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
        stats_fn: Callable[[HassioStatsData], ContainerStats | None],
        device_id: str,
        unique_id_prefix: str,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._container_id = container_id
        self._stats_fn = stats_fn
        self._attr_unique_id = f"{unique_id_prefix}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def _stats(self) -> ContainerStats | None:
        """Return the stats object for this entity's container."""
        return self._stats_fn(self.coordinator.data)

    @property
    def stats(self) -> ContainerStats:
        """Return the stats object, asserting it is available."""
        assert self._stats is not None
        return self._stats

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._stats is not None

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
        addon: AddonData,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._addon_slug = addon.addon.slug
        self._attr_unique_id = f"{addon.addon.slug}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, addon.addon.slug)})

    @property
    def addon_slug(self) -> str:
        """Return the add-on slug."""
        return self._addon_slug

    @property
    def addon_data(self) -> AddonData:
        """Return the add-on data, asserting it is available."""
        data = self.coordinator.data
        assert self._addon_slug in data.addons
        return data.addons[self._addon_slug]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._addon_slug in self.coordinator.data.addons

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
        return super().available and self.coordinator.data.os is not None

    @property
    def os(self) -> OSInfo:
        """Return the OS info object, asserting it is available."""
        assert self.coordinator.data.os is not None
        return self.coordinator.data.os


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
    def host(self) -> HostInfo:
        """Return the host info, asserting it is available."""
        assert self.coordinator.data.host is not None
        return self.coordinator.data.host


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
    def mount_name(self) -> str:
        """Return the mount name."""
        return self._mount.name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.mount_name in self.coordinator.data.mounts
