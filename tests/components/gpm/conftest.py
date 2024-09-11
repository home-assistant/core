"""Common fixtures for the GPM tests."""

from collections.abc import AsyncGenerator, Generator, Mapping
import logging
from pathlib import Path
import shutil
from unittest.mock import AsyncMock, MagicMock, patch

from git import Remote, Repo
import pytest

from homeassistant.components.gpm import get_manager
from homeassistant.components.gpm._manager import (
    IntegrationRepositoryManager,
    RepositoryManager,
    RepositoryType,
    ResourceRepositoryManager,
    UpdateStrategy,
)
from homeassistant.components.gpm.const import CONF_DOWNLOAD_URL, CONF_UPDATE_STRATEGY
from homeassistant.const import CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import TESTING_VERSIONS

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def repo() -> Generator[None, None, None]:
    """Mock socket oriented functions of git.Repo object."""

    repo = None

    def create_repo(_, working_dir: Path) -> Repo:
        """Create a dummy GIT repository containing structure required for HA integration.

        Parameters are the same as for git.Repo.clone_from - this function is used as a mock for it.

        Returns:
            A Python reference to the created repository.

        """
        nonlocal repo
        _LOGGER.debug("Creating a dummy GIT repository in %s", working_dir)
        repo = Repo.init(working_dir)
        component_dir = working_dir / "custom_components" / "awesome_component"
        component_dir.mkdir(parents=True)
        repo.index.add([component_dir])
        repo.index.commit("Initial commit")
        for tag in TESTING_VERSIONS:
            repo.index.commit(f"New version: {tag}")
            repo.create_tag(tag)
        return repo

    remote_mock = MagicMock(spec=Remote)
    remote_mock.fetch = MagicMock(return_value=None)
    with (
        patch(
            "homeassistant.components.gpm._manager.Repo.clone_from",
            side_effect=create_repo,
        ),
        patch(
            "homeassistant.components.gpm._manager.RepositoryManager._get_remote",
            return_value=remote_mock,
        ),
    ):
        yield

    if repo:
        _LOGGER.debug("Removing a dummy GIT repository in %s", repo.working_dir)
        shutil.rmtree(repo.working_dir, ignore_errors=True)


@pytest.fixture(params=["integration", "resource"])
def manager(request: pytest.FixtureRequest) -> None:
    """Fixture for both integration and resource managers."""
    return request.getfixturevalue(f"{request.param}_manager")


@pytest.fixture(name="integration_manager")
async def integration_manager_fixture(
    hass: HomeAssistant, repo: None
) -> AsyncGenerator[IntegrationRepositoryManager, None, None]:
    """Fixture for integration manager."""
    # every instance is created using homeassistant.components.gpm.get_manager()
    manager = _testing_integration_manager(hass)
    with patch(
        "homeassistant.components.gpm.IntegrationRepositoryManager",
        autospec=True,
        return_value=manager,
    ):
        yield manager
        await manager.remove()


@pytest.fixture(name="resource_manager")
async def resource_manager_fixture(
    hass: HomeAssistant, repo: None
) -> AsyncGenerator[ResourceRepositoryManager, None, None]:
    """Fixture for resource manager."""
    # lovelace is needed to test resource management
    assert await async_setup_component(hass, "lovelace", {})

    def async_download(_1, _2, install_path: Path) -> None:
        install_path.touch()

    manager = _testing_resource_manager(hass)
    # every instance is created using homeassistant.components.gpm.get_manager()
    with (
        patch(
            "homeassistant.components.gpm.ResourceRepositoryManager",
            autospec=True,
            return_value=manager,
        ),
        patch(
            "homeassistant.components.gpm._manager.async_download",
            side_effect=async_download,
        ),
    ):
        yield manager
        await manager.remove()


def _testing_integration_manager(
    hass: HomeAssistant,
) -> IntegrationRepositoryManager:
    return _testing_manager(
        hass,
        {
            CONF_TYPE: RepositoryType.INTEGRATION,
            CONF_URL: "https://github.com/user/awesome-component",
            CONF_UPDATE_STRATEGY: UpdateStrategy.LATEST_TAG,
        },
    )


def _testing_resource_manager(
    hass: HomeAssistant,
) -> ResourceRepositoryManager:
    return _testing_manager(
        hass,
        {
            CONF_TYPE: RepositoryType.RESOURCE,
            CONF_URL: "https://github.com/user/awesome-card",
            CONF_UPDATE_STRATEGY: UpdateStrategy.LATEST_TAG,
            CONF_DOWNLOAD_URL: "https://github.com/user/awesome-card/releases/download/{{ version }}/bundle.js",
        },
    )


def _testing_manager(hass: HomeAssistant, data: Mapping[str, str]) -> RepositoryManager:
    """Get the RepositoryManager for testing.

    Uses the same interface as homeassistant.components.gpm.get_manager().
    """
    manager = get_manager(hass, data)
    for method in (
        "clone",
        "fetch",
        "checkout",
        "install",
        "update",
        "uninstall",
        "is_cloned",
        "is_installed",
        "remove",
        "get_current_version",
        "get_latest_version",
    ):
        setattr(manager, method, AsyncMock(wraps=getattr(manager, method)))
    return manager


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gpm.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
