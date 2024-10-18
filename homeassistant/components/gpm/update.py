"""Update entities for GPM."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GPMConfigEntry
from ._manager import (
    CheckoutError,
    IntegrationRepositoryManager,
    RepositoryManager,
    UpdateStrategy,
    VersionAlreadyInstalledError,
)
from .const import GIT_SHORT_HASH_LEN

SCAN_INTERVAL = timedelta(hours=3)
PARALLEL_UPDATES = 0  # = unlimited


async def async_setup_entry(  # noqa: D103
    hass: HomeAssistant,
    entry: GPMConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    manager: RepositoryManager = entry.runtime_data
    async_add_entities([GPMUpdateEntity(manager)], True)


class GPMUpdateEntity(UpdateEntity):
    """Update entities for packages downloaded with GPM."""

    _attr_has_entity_name = True

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.SPECIFIC_VERSION
    )

    def __init__(self, manager: RepositoryManager) -> None:  # noqa: D107
        super().__init__()
        self.manager = manager
        self._component_name: str | None = None

    async def async_update(self) -> None:
        """Update state."""
        await self.manager.fetch()

        if isinstance(self.manager, IntegrationRepositoryManager):
            self._component_name = await self.manager.get_component_name()

        current = await self.manager.get_current_version()
        latest = await self.manager.get_latest_version()
        if self.manager.update_strategy == UpdateStrategy.LATEST_COMMIT:
            self._attr_installed_version = current[:GIT_SHORT_HASH_LEN]
            self._attr_latest_version = latest[:GIT_SHORT_HASH_LEN]
        else:
            self._attr_installed_version = current
            self._attr_latest_version = latest

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.manager.unique_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.manager.slug

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend."""
        if self._component_name:
            return f"https://brands.home-assistant.io/_/{self._component_name}/icon.png"
        return None

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        try:
            await self.manager.update(version)
        except VersionAlreadyInstalledError as e:
            raise HomeAssistantError(e) from e
        except CheckoutError as e:
            raise HomeAssistantError(f"Version `{version}` not found") from e
