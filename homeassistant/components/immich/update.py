"""Update platform for the Immich integration."""

from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ImmichConfigEntry, ImmichDataUpdateCoordinator
from .entity import ImmichEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add immich server update entity."""
    coordinator = entry.runtime_data

    if coordinator.data.server_version_check is not None:
        async_add_entities([ImmichUpdateEntity(coordinator)])


class ImmichUpdateEntity(ImmichEntity, UpdateEntity):
    """Define Immich update entity."""

    _attr_translation_key = "update"

    def __init__(
        self,
        coordinator: ImmichDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_update"

    @property
    def installed_version(self) -> str:
        """Current installed immich server version."""
        return self.coordinator.data.server_about.version

    @property
    def latest_version(self) -> str | None:
        """Available new immich server version."""
        assert self.coordinator.data.server_version_check
        return self.coordinator.data.server_version_check.release_version

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the new immich server version."""
        return (
            f"https://github.com/immich-app/immich/releases/tag/{self.latest_version}"
        )
