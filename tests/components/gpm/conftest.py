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
from typing import Generic


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gpm.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


def _mock_manager[T](hass: HomeAssistant, cls: Generic[T]) -> Generator[T, None, None]:
    """Mock the GPM manager."""
    manager = cls(
        hass,
        "https://github.com/user/awesome-component",
        UpdateStrategy.LATEST_TAG,
    )
    manager.clone = AsyncMock(return_value=None)
    manager.checkout = AsyncMock(return_value=None)
    manager.install = AsyncMock(return_value=None)
    manager.is_cloned = AsyncMock(return_value=True)
    manager.is_installed = AsyncMock(return_value=False)
    manager.get_component_dir = AsyncMock(
        return_value=Path(
            "/config/gpm/awesome_component/custom_components/awesome_component"
        )
    )
    manager.get_latest_version = AsyncMock(return_value="v1.0.0")
    with patch(
        "homeassistant.components.gpm.get_manager",
        return_value=manager,
    ) as mock:
        yield mock.return_value


@pytest.fixture
def mock_integration_manager(
    hass: HomeAssistant,
) -> Generator[IntegrationRepositoryManager, None, None]:
    """Mock the GPM manager."""
    yield from _mock_manager(hass, IntegrationRepositoryManager)


@pytest.fixture
def mock_resource_manager(
    hass: HomeAssistant,
) -> Generator[ResourceRepositoryManager, None, None]:
    """Mock the GPM manager."""
    yield from _mock_manager(hass, ResourceRepositoryManager)
