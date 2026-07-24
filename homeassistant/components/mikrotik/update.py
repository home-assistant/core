"""Support for update entities."""

from dataclasses import dataclass
from typing import Any, cast, override

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_ROUTERBOARD_FIRMWARE,
    ATTR_SYSTEM_FIRMWARE,
    BACKUP,
    MIKROTIK_SERVICES,
    ROUTERBOARD,
    UPDATE,
)
from .coordinator import MikrotikConfigEntry, mikrotik_config_entry_errors
from .entity import MikrotikEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MikrotikUpdateEntityDescription(UpdateEntityDescription):
    """Shared Mikrotik Update entity description."""

    release_notes: str | None = None
    supported_features: UpdateEntityFeature
    path: str
    installed_version: str
    latest_version: str


UPDATES = {
    MikrotikUpdateEntityDescription(
        key="fw-update",
        translation_key="firmware_update",
        entity_category=EntityCategory.CONFIG,
        supported_features=UpdateEntityFeature.INSTALL | UpdateEntityFeature.BACKUP,
        path=UPDATE,
        installed_version=ATTR_SYSTEM_FIRMWARE,
        latest_version="latest-version",
        release_notes="https://cdn.mikrotik.com/routeros/{version}/CHANGELOG",
    ),
    MikrotikUpdateEntityDescription(
        key="routerboard-update",
        translation_key="routerboard_update",
        entity_category=EntityCategory.CONFIG,
        supported_features=UpdateEntityFeature.INSTALL,
        path=ROUTERBOARD,
        installed_version=ATTR_ROUTERBOARD_FIRMWARE,
        latest_version="upgrade-firmware",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MikrotikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Mikrotik update entities."""

    coordinator = entry.runtime_data

    update_list = [
        MikrotikUpdateEntity(coordinator, update_desc)
        for update_desc in UPDATES
        if update_desc.path in coordinator.api.system
    ]

    async_add_entities(update_list)


class MikrotikUpdateEntity(MikrotikEntity, UpdateEntity):
    """Mixin for update entity specific attributes."""

    update_description: MikrotikUpdateEntityDescription

    @property
    @override
    def supported_features(self) -> UpdateEntityFeature:
        """Flag supported features."""
        return cast(UpdateEntityFeature, self.entity_description.supported_features)

    @property
    def _device_path_info(self) -> dict[str, Any]:
        return cast(
            dict[str, Any], self.coordinator.api.system[self.entity_description.path]
        )

    @property
    @override
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self._device_path_info.get(self.entity_description.installed_version)

    @property
    @override
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if latest_version := self._device_path_info.get(
            self.entity_description.latest_version
        ):
            return cast(str | None, latest_version)
        return self._device_path_info.get(self.entity_description.installed_version)

    @property
    @override
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        if self.entity_description.release_notes:
            return str(self.entity_description.release_notes).format(
                version=self.latest_version
            )
        return None

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        with mikrotik_config_entry_errors():
            if backup:
                await self.hass.async_add_executor_job(
                    self.coordinator.api.command,
                    MIKROTIK_SERVICES[BACKUP],
                )
            await self.hass.async_add_executor_job(
                self.coordinator.api.command,
                MIKROTIK_SERVICES[self.entity_description.key],
            )
