"""Common fixtures for the GPM tests."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.gpm._manager import (
    IntegrationRepositoryManager,
    ResourceRepositoryManager,
    UpdateStrategy,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gpm.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_integration_manager(
    hass: HomeAssistant,
) -> Generator[IntegrationRepositoryManager, None, None]:
    """Mock GPM manager."""
    manager = IntegrationRepositoryManager(
        hass,
        "https://github.com/user/awesome-component",
        UpdateStrategy.LATEST_TAG,
    )
    manager.clone = AsyncMock(return_value=None)
    manager.fetch = AsyncMock(return_value=None)
    manager.checkout = AsyncMock(return_value=None)
    manager.install = AsyncMock(return_value=None)
    manager.is_cloned = AsyncMock(return_value=True)
    manager.is_installed = AsyncMock(return_value=False)
    manager.remove = AsyncMock(return_value=None)
    manager.get_component_dir = AsyncMock(
        return_value=Path(
            "/config/gpm/awesome_component/custom_components/awesome_component"
        )
    )
    manager.get_current_version = AsyncMock(return_value="v0.9.9")
    manager.get_latest_version = AsyncMock(return_value="v1.0.0")
    with patch(
        "homeassistant.components.gpm.IntegrationRepositoryManager",
        autospec=True,
        return_value=manager,
    ) as mock:
        yield mock.return_value


@pytest.fixture
def mock_resource_manager(
    hass: HomeAssistant,
) -> Generator[ResourceRepositoryManager, None, None]:
    """Mock the GPM manager."""
    manager = ResourceRepositoryManager(
        hass,
        "https://github.com/user/awesome-card",
        UpdateStrategy.LATEST_TAG,
    )
    manager.set_download_url(
        "https://github.com/user/awesome-card/releases/download/{{ version }}/bundle.js"
    )
    manager.clone = AsyncMock(return_value=None)
    manager.fetch = AsyncMock(return_value=None)
    manager.checkout = AsyncMock(return_value=None)
    manager.install = AsyncMock(return_value=None)
    manager.is_cloned = AsyncMock(return_value=True)
    manager.is_installed = AsyncMock(return_value=False)
    manager.remove = AsyncMock(return_value=None)
    manager.get_current_version = AsyncMock(return_value="v0.9.9")
    manager.get_latest_version = AsyncMock(return_value="v1.0.0")
    with patch(
        "homeassistant.components.gpm.ResourceRepositoryManager",
        autospec=True,
        return_value=manager,
    ) as mock:
        yield mock.return_value
