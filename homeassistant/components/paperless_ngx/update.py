"""Update platform for Paperless-ngx."""

from __future__ import annotations

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PaperlessConfigEntry, PaperlessCoordinator
from .entity import PaperlessEntity

PAPERLESS_CHANGELOGS = "https://docs.paperless-ngx.com/changelog/"


PARALLEL_UPDATES = 0

UPDATE_ENTITY_DESCRIPTIONS: tuple[UpdateEntityDescription, ...] = (
    UpdateEntityDescription(
        key="paperless_update",
        translation_key="paperless_update",
        device_class=UpdateDeviceClass.FIRMWARE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Paperless-ngx update entities."""

    async_add_entities(
        PaperlessUpdateEntity(
            coordinator=entry.runtime_data,
            entry=entry,
            description=description,
        )
        for description in UPDATE_ENTITY_DESCRIPTIONS
    )


class PaperlessUpdateEntity(PaperlessEntity, UpdateEntity):
    """Defines a Paperless-ngx update entity."""

    _attr_supported_features = UpdateEntityFeature(0)

    def __init__(
        self,
        entry: PaperlessConfigEntry,
        coordinator: PaperlessCoordinator,
        description: UpdateEntityDescription,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            description=description,
        )

        self.release_url = PAPERLESS_CHANGELOGS

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        remote_version = self.coordinator.data.remote_version
        return (
            super().available
            and remote_version is not None
            and remote_version.update_available is not None
        )

    @property
    def installed_version(self) -> str | None:
        """Return the installed version."""
        return self.coordinator.api.host_version

    @property
    def latest_version(self) -> str | None:
        """Return the latest version available."""
        remote_version = self.coordinator.data.remote_version
        return (
            remote_version.version.lstrip("v")
            if remote_version and remote_version.version
            else None
        )
