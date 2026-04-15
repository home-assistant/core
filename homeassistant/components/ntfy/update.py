"""Update platform for the ntfy integration."""

from __future__ import annotations

from enum import StrEnum

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import CONF_URL, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NTFY_KEY
from .const import DEFAULT_URL
from .coordinator import (
    NtfyConfigEntry,
    NtfyLatestReleaseUpdateCoordinator,
    NtfyVersionDataUpdateCoordinator,
)
from .entity import NtfyCommonBaseEntity

PARALLEL_UPDATES = 0


class NtfyUpdate(StrEnum):
    """Ntfy update."""

    UPDATE = "update"


DESCRIPTION = UpdateEntityDescription(
    key=NtfyUpdate.UPDATE,
    translation_key=NtfyUpdate.UPDATE,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NtfyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up update platform."""
    if (
        entry.data[CONF_URL] != DEFAULT_URL
        and (version_coordinator := entry.runtime_data.version).data is not None
    ):
        update_coordinator = hass.data[NTFY_KEY]
        async_add_entities(
            [NtfyUpdateEntity(version_coordinator, update_coordinator, DESCRIPTION)]
        )


class NtfyUpdateEntity(NtfyCommonBaseEntity, UpdateEntity):
    """Representation of an update entity."""

    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES
    coordinator: NtfyVersionDataUpdateCoordinator

    def __init__(
        self,
        coordinator: NtfyVersionDataUpdateCoordinator,
        update_checker: NtfyLatestReleaseUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, description)
        self.update_checker = update_checker
        if self._attr_device_info and self.installed_version:
            self._attr_device_info.update({"sw_version": self.installed_version})

    @property
    def installed_version(self) -> str | None:
        """Current version."""
        return self.coordinator.data.version if self.coordinator.data else None

    @property
    def title(self) -> str | None:
        """Title of the release."""

        return f"ntfy {self.update_checker.data.name}"

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes."""

        return self.update_checker.data.html_url

    @property
    def latest_version(self) -> str | None:
        """Latest version."""

        return self.update_checker.data.tag_name.removeprefix("v")

    async def async_release_notes(self) -> str | None:
        """Return the release notes."""
        return self.update_checker.data.body

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass.

        Register extra update listener for the update checker coordinator.
        """
        await super().async_added_to_hass()
        self.async_on_remove(
            self.update_checker.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.update_checker.last_update_success
