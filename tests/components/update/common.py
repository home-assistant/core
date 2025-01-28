"""Common test fixtures for the update component test."""

import logging
from typing import Any

from homeassistant.components.update import UpdateEntity

_LOGGER = logging.getLogger(__name__)


class MockUpdateEntity(UpdateEntity):
    """Mock UpdateEntity class."""

    def __init__(self, **values: Any) -> None:
        """Initialize an entity."""
        for key, val in values.items():
            setattr(self, f"_attr_{key}", val)

    def install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Install an update."""
        if backup:
            _LOGGER.info("Creating backup before installing update")

        if version is not None:
            self._attr_installed_version = version
            _LOGGER.info("Installed update with version: %s", version)
        else:
            self._attr_installed_version = self.latest_version
            _LOGGER.info("Installed latest update")

    def release_notes(self) -> str | None:
        """Return the release notes of the latest version."""
        return "Release notes"
