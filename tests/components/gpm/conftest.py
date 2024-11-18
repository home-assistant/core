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
from homeassistant.components.gpm.const import (
    CONF_DOWNLOAD_URL,
    CONF_UPDATE_STRATEGY,
    DOMAIN,
)
from homeassistant.const import CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import DEFAULT_VERSION, TESTING_VERSIONS

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def repo() -> Generator[None]:
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
        repo.git.checkout(DEFAULT_VERSION)
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
    hass: HomeAssistant, repo: None, tmp_path: Path
) -> AsyncGenerator[IntegrationRepositoryManager]:
    """Fixture for integration manager."""
    # every instance is created using homeassistant.components.gpm.get_manager()
    manager = _testing_integration_manager(hass, tmp_path)
    with patch(
        "homeassistant.components.gpm.IntegrationRepositoryManager",
        autospec=True,
        return_value=manager,
    ):
        yield manager
        await manager.remove()


@pytest.fixture(name="resource_manager")
async def resource_manager_fixture(
    hass: HomeAssistant, repo: None, tmp_path: Path
) -> AsyncGenerator[ResourceRepositoryManager]:
    """Fixture for resource manager."""
    # lovelace is needed to test resource management
    assert await async_setup_component(hass, "lovelace", {})

    def async_download(_1, _2, install_path: Path) -> None:
        install_path.touch()

    manager = _testing_resource_manager(hass, tmp_path)
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
    hass: HomeAssistant, tmp_path: Path
) -> IntegrationRepositoryManager:
    return _testing_manager(
        hass,
        {
            CONF_TYPE: RepositoryType.INTEGRATION,
            CONF_URL: "https://github.com/user/awesome-component",
            CONF_UPDATE_STRATEGY: UpdateStrategy.LATEST_TAG,
        },
        tmp_path,
    )


def _testing_resource_manager(
    hass: HomeAssistant, tmp_path: Path
) -> ResourceRepositoryManager:
    return _testing_manager(
        hass,
        {
            CONF_TYPE: RepositoryType.RESOURCE,
            CONF_URL: "https://github.com/user/awesome-card",
            CONF_UPDATE_STRATEGY: UpdateStrategy.LATEST_TAG,
            CONF_DOWNLOAD_URL: "https://github.com/user/awesome-card/releases/download/{{ version }}/bundle.js",
        },
        tmp_path,
    )


def _testing_manager(
    hass: HomeAssistant, data: Mapping[str, str], tmp_path: Path
) -> RepositoryManager:
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
        "get_download_url",
    ):
        if not hasattr(manager, method):
            continue
        setattr(manager, method, AsyncMock(wraps=getattr(manager, method)))
    manager.clone_basedir = tmp_path / "clone_basedir"
    manager.clone_basedir.mkdir()
    manager.install_basedir = tmp_path / "install_basedir"
    manager.install_basedir.mkdir()
    return manager


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gpm.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def config_entry(
    hass: HomeAssistant,
    integration_manager: IntegrationRepositoryManager,
) -> MockConfigEntry:
    """Set up the GPM integration, add it as a config entry into hass and return the entry."""
    await integration_manager.install()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: RepositoryType.INTEGRATION,
            CONF_URL: integration_manager.repo_url,
            CONF_UPDATE_STRATEGY: integration_manager.update_strategy,
        },
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
