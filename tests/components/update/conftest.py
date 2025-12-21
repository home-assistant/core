"""Fixtures for update component testing."""

import pytest

from homeassistant.components.update import UpdateEntityFeature

from .common import MockUpdateEntity


@pytest.fixture
def mock_update_entities() -> list[MockUpdateEntity]:
    """Return a list of mock update entities."""
    return [
        MockUpdateEntity(
            name="No Update",
            unique_id="no_update",
            installed_version="1.0.0",
            latest_version="1.0.0",
            supported_features=UpdateEntityFeature.INSTALL,
        ),
        MockUpdateEntity(
            name="Update Available",
            unique_id="update_available",
            installed_version="1.0.0",
            latest_version="1.0.1",
            supported_features=UpdateEntityFeature.INSTALL,
        ),
        MockUpdateEntity(
            name="Update Unknown",
            unique_id="update_unknown",
            installed_version="1.0.0",
            latest_version=None,
            supported_features=UpdateEntityFeature.INSTALL,
        ),
        MockUpdateEntity(
            name="Update Specific Version",
            unique_id="update_specific_version",
            installed_version="1.0.0",
            latest_version="1.0.0",
            supported_features=UpdateEntityFeature.INSTALL
            | UpdateEntityFeature.SPECIFIC_VERSION,
        ),
        MockUpdateEntity(
            name="Update Backup",
            unique_id="update_backup",
            installed_version="1.0.0",
            latest_version="1.0.1",
            supported_features=UpdateEntityFeature.INSTALL
            | UpdateEntityFeature.SPECIFIC_VERSION
            | UpdateEntityFeature.BACKUP,
        ),
        MockUpdateEntity(
            name="Update Already in Progress",
            unique_id="update_already_in_progress",
            installed_version="1.0.0",
            latest_version="1.0.1",
            in_progress=True,
            supported_features=UpdateEntityFeature.INSTALL
            | UpdateEntityFeature.PROGRESS,
            update_percentage=50,
        ),
        MockUpdateEntity(
            name="Update Already in Progress Float",
            unique_id="update_already_in_progress_float",
            installed_version="1.0.0",
            latest_version="1.0.1",
            in_progress=True,
            supported_features=UpdateEntityFeature.INSTALL
            | UpdateEntityFeature.PROGRESS,
            update_percentage=0.25,
            display_precision=2,
        ),
        MockUpdateEntity(
            name="Update No Install",
            unique_id="no_install",
            installed_version="1.0.0",
            latest_version="1.0.1",
        ),
        MockUpdateEntity(
            name="Update with release notes",
            unique_id="with_release_notes",
            installed_version="1.0.0",
            latest_version="1.0.1",
            supported_features=UpdateEntityFeature.RELEASE_NOTES,
        ),
        MockUpdateEntity(
            name="Update with auto update",
            unique_id="with_auto_update",
            installed_version="1.0.0",
            latest_version="1.0.1",
            auto_update=True,
            supported_features=UpdateEntityFeature.INSTALL,
        ),
    ]
