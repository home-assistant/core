"""
Provide a mock update platform.

Call init before using it in your tests to ensure clean test data.
"""
from __future__ import annotations

import logging

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature

from tests.common import MockEntity

ENTITIES = []

_LOGGER = logging.getLogger(__name__)


class MockUpdateEntity(MockEntity, UpdateEntity):
    """Mock UpdateEntity class."""

    @property
    def current_version(self) -> str | None:
        """Version currently in use."""
        return self._handle("current_version")

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

    def install(
        self,
        version: str | None = None,
        backup: bool | None = None,
    ) -> None:
        """Install an update."""
        if backup:
            _LOGGER.info("Creating backup before installing update")

        if version is not None:
            self._values["current_version"] = version
            _LOGGER.info(f"Installed update with version: {version}")
        else:
            self._values["current_version"] = self.latest_version
            _LOGGER.info("Installed latest update")


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        []
        if empty
        else [
            MockUpdateEntity(
                name="No Update",
                unique_id="no_update",
                current_version="1.0.0",
                latest_version="1.0.0",
                supported_features=UpdateEntityFeature.INSTALL,
            ),
            MockUpdateEntity(
                name="Update Available",
                unique_id="update_available",
                current_version="1.0.0",
                latest_version="1.0.1",
                supported_features=UpdateEntityFeature.INSTALL,
            ),
            MockUpdateEntity(
                name="Update Unknown",
                unique_id="update_unknown",
                current_version="1.0.0",
                latest_version=None,
                supported_features=UpdateEntityFeature.INSTALL,
            ),
            MockUpdateEntity(
                name="Update Specific Version",
                unique_id="update_specific_version",
                current_version="1.0.0",
                latest_version="1.0.0",
                supported_features=UpdateEntityFeature.INSTALL
                | UpdateEntityFeature.SPECIFIC_VERSION,
            ),
            MockUpdateEntity(
                name="Update Backup",
                unique_id="update_backup",
                current_version="1.0.0",
                latest_version="1.0.1",
                supported_features=UpdateEntityFeature.INSTALL
                | UpdateEntityFeature.SPECIFIC_VERSION
                | UpdateEntityFeature.BACKUP,
            ),
            MockUpdateEntity(
                name="Update Already in Progress",
                unique_id="update_already_in_progres",
                current_version="1.0.0",
                latest_version="1.0.1",
                in_progress=50,
                supported_features=UpdateEntityFeature.INSTALL
                | UpdateEntityFeature.PROGRESS,
            ),
            MockUpdateEntity(
                name="Update No Install",
                unique_id="no_install",
                current_version="1.0.0",
                latest_version="1.0.1",
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)
