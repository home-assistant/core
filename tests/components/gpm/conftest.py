"""Common fixtures for the GPM tests."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from git import Repo
import pytest

from homeassistant.components.gpm._manager import (
    IntegrationRepositoryManager,
    ResourceRepositoryManager,
    UpdateStrategy,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
def repo() -> Generator[Repo, None, None]:
    """Mock git.Repo object."""

    def clone_from(repo_url: str, working_dir: Path) -> Path:
        """Create a fake GIT repository."""
        (working_dir / ".git").mkdir(parents=True)
        component_dir = working_dir / "custom_components" / "awesome_component"
        component_dir.mkdir(parents=True)
        return working_dir

    with patch(
        "homeassistant.components.gpm._manager.Repo",
        autospec=True,
    ) as mock:
        mock.clone_from = MagicMock(return_value=mock, side_effect=clone_from)
        yield mock.return_value


@pytest.fixture
def integration_manager(
    hass: HomeAssistant, tmp_path: Path, repo: Repo
) -> Generator[IntegrationRepositoryManager, None, None]:
    """Mock GPM manager."""
    manager = IntegrationRepositoryManager(
        hass,
        "https://github.com/user/awesome-component",
        UpdateStrategy.LATEST_TAG,
    )
    (clone_basedir := tmp_path / "clone").mkdir()
    manager.clone_basedir = clone_basedir
    (install_basedir := tmp_path / "install").mkdir()
    manager.install_basedir = install_basedir
    manager.clone = AsyncMock(wraps=manager.clone)
    manager.fetch = AsyncMock(return_value=None)
    manager.checkout = AsyncMock(return_value=None)
    manager.install = AsyncMock(wraps=manager.install)
    manager.uninstall = AsyncMock(wraps=manager.uninstall)
    manager.is_cloned = AsyncMock(wraps=manager.is_cloned)
    manager.is_installed = AsyncMock(wraps=manager.is_installed)
    manager.remove = AsyncMock(wraps=manager.remove)
    manager.get_current_version = AsyncMock(return_value="v0.9.9")
    manager.get_latest_version = AsyncMock(return_value="v1.0.0")
    # every instance is created using homeassistant.components.gpm.get_manager()
    with patch(
        "homeassistant.components.gpm.IntegrationRepositoryManager",
        autospec=True,
        return_value=manager,
    ) as mock:
        yield mock.return_value


@pytest.fixture
def resource_manager(
    hass: HomeAssistant, tmp_path: Path, repo: MagicMock
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
    (clone_basedir := tmp_path / "clone").mkdir()
    manager.clone_basedir = clone_basedir
    (install_basedir := tmp_path / "install").mkdir()
    manager.install_basedir = install_basedir
    manager.clone = AsyncMock(wraps=manager.clone)
    manager.fetch = AsyncMock(return_value=None)
    manager.checkout = AsyncMock(return_value=None)
    manager.install = AsyncMock(return_value=None)
    manager.uninstall = AsyncMock(wraps=manager.uninstall)
    manager.is_cloned = AsyncMock(wraps=manager.is_cloned)
    manager.is_installed = AsyncMock(wraps=manager.is_installed)
    manager.remove = AsyncMock(wraps=manager.remove)
    manager.get_current_version = AsyncMock(return_value="v0.9.9")
    manager.get_latest_version = AsyncMock(return_value="v1.0.0")
    # every instance is created using homeassistant.components.gpm.get_manager()
    with patch(
        "homeassistant.components.gpm.ResourceRepositoryManager",
        autospec=True,
        return_value=manager,
    ) as mock:
        yield mock.return_value


@pytest.fixture(params=["integration", "resource"])
def manager(request: pytest.FixtureRequest) -> None:
    """Fixture for both integration and resource managers."""
    return request.getfixturevalue(f"{request.param}_manager")


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gpm.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
