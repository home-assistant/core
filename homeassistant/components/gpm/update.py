"""Update entities for GPM."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import create_issue

from . import GPMConfigEntry
from ._manager import (
    GPMError,
    IntegrationRepositoryManager,
    RepositoryManager,
    UpdateStrategy,
)
from .const import DOMAIN, GIT_SHORT_HASH_LEN
from .repairs import create_restart_issue

SCAN_INTERVAL = timedelta(hours=3)
PARALLEL_UPDATES = 0  # = unlimited


async def async_setup_entry(  # noqa: D103
    hass: HomeAssistant,
    entry: GPMConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    manager: RepositoryManager = entry.runtime_data
    async_add_entities([GPMUpdateEntity(manager)], update_before_add=True)


class GPMUpdateEntity(UpdateEntity):
    """Update entities for packages downloaded with GPM."""

    _attr_has_entity_name = True

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.SPECIFIC_VERSION
    )

    def __init__(self, manager: RepositoryManager) -> None:  # noqa: D107
        self.manager = manager
        self._first_update = True
        self._component_name: str | None = None

    def update(self) -> None:
        """Update state."""
        # used inside (sync) update method because RepositoryManager methods are not async
        if self._first_update:
            self._first_update = False
        else:
            self.manager.fetch()
        self._attr_unique_id = f"{DOMAIN}_{self.manager.slug}"
        self._attr_name = self.manager.slug

        if isinstance(self.manager, IntegrationRepositoryManager):
            self._component_name = self.manager.component_name

        current = self.manager.get_current_version()
        latest = self.manager.get_latest_version()
        if self.manager.update_strategy == UpdateStrategy.LATEST_COMMIT:
            self._attr_installed_version = current[:GIT_SHORT_HASH_LEN]
            self._attr_latest_version = latest[:GIT_SHORT_HASH_LEN]
        else:
            self._attr_installed_version = current
            self._attr_latest_version = latest

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend."""
        if self._component_name:
            return f"https://brands.home-assistant.io/_/{self._component_name}/icon.png"
        return None

    def install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Install an update."""
        to_install = version or self.latest_version
        if to_install == self.installed_version:
            raise HomeAssistantError(
                f"Version `{self.installed_version}` of `{self.name}` is already downloaded"
            )
        try:
            self.manager.checkout(to_install)
        except GPMError as e:
            raise HomeAssistantError(e) from e

        create_restart_issue(
            create_issue,
            self.hass,
            action="update",
            name=cast(str, self.name),
            issue_domain=self._component_name,
        )
