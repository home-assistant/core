"""Support for update entities of a Pi-hole system."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from hole import Hole

from homeassistant.components.update import UpdateEntity, UpdateEntityDescription
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleConfigEntry
from .entity import PiHoleEntity


@dataclass(frozen=True)
class PiHoleUpdateEntityDescription(UpdateEntityDescription):
    """Describes PiHole update entity."""

    installed_version: Callable[[dict], str | None] = lambda api: None
    latest_version: Callable[[dict], str | None] = lambda api: None
    has_update: Callable[[dict], bool | None] = lambda api: None
    release_base_url: str | None = None
    title: str | None = None


UPDATE_ENTITY_TYPES: tuple[PiHoleUpdateEntityDescription, ...] = (
    PiHoleUpdateEntityDescription(
        key="core_update_available",
        translation_key="core_update_available",
        title="Pi-hole Core",
        entity_category=EntityCategory.DIAGNOSTIC,
        installed_version=lambda versions: versions.get("core_current"),
        latest_version=lambda versions: versions.get("core_latest"),
        has_update=lambda versions: versions.get("core_update"),
        release_base_url="https://github.com/pi-hole/pi-hole/releases/tag",
    ),
    PiHoleUpdateEntityDescription(
        key="web_update_available",
        translation_key="web_update_available",
        title="Pi-hole Web interface",
        entity_category=EntityCategory.DIAGNOSTIC,
        installed_version=lambda versions: versions.get("web_current"),
        latest_version=lambda versions: versions.get("web_latest"),
        has_update=lambda versions: versions.get("web_update"),
        release_base_url="https://github.com/pi-hole/AdminLTE/releases/tag",
    ),
    PiHoleUpdateEntityDescription(
        key="ftl_update_available",
        translation_key="ftl_update_available",
        title="Pi-hole FTL DNS",
        entity_category=EntityCategory.DIAGNOSTIC,
        installed_version=lambda versions: versions.get("FTL_current"),
        latest_version=lambda versions: versions.get("FTL_latest"),
        has_update=lambda versions: versions.get("FTL_update"),
        release_base_url="https://github.com/pi-hole/FTL/releases/tag",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiHoleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pi-hole update entities."""
    name = entry.data[CONF_NAME]
    hole_data = entry.runtime_data

    async_add_entities(
        PiHoleUpdateEntity(
            hole_data.api,
            hole_data.coordinator,
            name,
            entry.entry_id,
            description,
        )
        for description in UPDATE_ENTITY_TYPES
    )


class PiHoleUpdateEntity(PiHoleEntity, UpdateEntity):
    """Representation of a Pi-hole update entity."""

    entity_description: PiHoleUpdateEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        api: Hole,
        coordinator: DataUpdateCoordinator[None],
        name: str,
        server_unique_id: str,
        description: PiHoleUpdateEntityDescription,
    ) -> None:
        """Initialize a Pi-hole update entity."""
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description

        self._attr_unique_id = f"{self._server_unique_id}/{description.key}"
        self._attr_title = description.title

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        if isinstance(self.api.versions, dict):
            return self.entity_description.installed_version(self.api.versions)
        return None

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if isinstance(self.api.versions, dict):
            if self.entity_description.has_update(self.api.versions):
                return self.entity_description.latest_version(self.api.versions)
            return self.installed_version
        return None

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        if self.latest_version:
            return f"{self.entity_description.release_base_url}/{self.latest_version}"
        return None
