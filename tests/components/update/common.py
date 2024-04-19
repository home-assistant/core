"""Common test fixtures for the update component test."""

import logging
from typing import Any

from homeassistant.components.update import UpdateEntity

from tests.common import MockEntity

_LOGGER = logging.getLogger(__name__)


class MockUpdateEntity(MockEntity, UpdateEntity):
    """Mock UpdateEntity class."""

    @property
    def auto_update(self) -> bool:
        """Indicate if the device or service has auto update enabled."""
        return self._handle("auto_update")

    @property
    def installed_version(self) -> str | None:
        """Version currently installed and in use."""
        return self._handle("installed_version")

    @property
    def in_progress(self) -> bool | int | None:
        """Update installation progress."""
        return self._handle("in_progress")

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self._handle("latest_version")

    @property
    def release_summary(self) -> str | None:
        """Summary of the release notes or changelog."""
        return self._handle("release_summary")

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        return self._handle("release_url")

    @property
    def title(self) -> str | None:
        """Title of the software."""
        return self._handle("title")

    def install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Install an update."""
        if backup:
            _LOGGER.info("Creating backup before installing update")

        if version is not None:
            self._values["installed_version"] = version
            _LOGGER.info("Installed update with version: %s", version)
        else:
            self._values["installed_version"] = self.latest_version
            _LOGGER.info("Installed latest update")

    def release_notes(self) -> str | None:
        """Return the release notes of the latest version."""
        return "Release notes"
