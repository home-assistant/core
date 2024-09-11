"""GitPython wrapper to manage GIT repos as HA integrations / resources.

When we speak about "version" in this file, we mean either a tag or a commit hash.
"""

from abc import abstractmethod
from collections.abc import AsyncGenerator, Callable, Iterable
import contextlib
from enum import StrEnum, auto
import functools
import logging
from pathlib import Path
import shutil
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientError
from awesomeversion import AwesomeVersion
from git import GitCommandError, Remote, Repo

from homeassistant.components.lovelace.const import (  # pylint: disable=hass-component-root-import
    DOMAIN as LOVELACE_DOMAIN,
)
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.const import EVENT_LOVELACE_UPDATED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.template import Template
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    DOWNLOAD_CHUNK_SIZE,
    PATH_CLONE_BASEDIR,
    PATH_INTEGRATION_INSTALL_BASEDIR,
    PATH_RESOURCE_INSTALL_BASEDIR,
    URL_BASE,
)

_LOGGER = logging.getLogger(__name__)


class RepositoryType(StrEnum):
    """Type of GIT repo."""

    INTEGRATION = auto()
    RESOURCE = auto()


class UpdateStrategy(StrEnum):
    """Determines strategy for how to pick new versions to install."""

    LATEST_TAG = auto()
    """Install the latest stable tag."""

    LATEST_UNSTABLE_TAG = auto()
    """Install the latest tag, including dev, alpha, beta and RC versions."""

    LATEST_COMMIT = auto()
    """Install the latest commit from default branch."""


class RepositoryManager:
    """Manage GIT repo as a HA integration / resource."""

    def __init__(
        self,
        hass: HomeAssistant,
        repo_url: str,
        clone_basedir: Path | str,
        install_basedir: Path | str,
        update_strategy: UpdateStrategy,
    ) -> None:
        self.hass = hass
        self.repo_url = repo_url
        self.clone_basedir = Path(clone_basedir)
        self.install_basedir = Path(install_basedir)
        self.update_strategy = update_strategy
        self._current_version_cache: str | None = None
        self._latest_version_cache: str | None = None
        self.__repo: Repo | None = None

    async def is_cloned(self) -> bool:
        """Return True if the GIT repo is cloned."""
        try:
            git_dir = self.working_dir / ".git"
            return await self.hass.async_add_executor_job(git_dir.exists)
        except OSError:
            return False

    @staticmethod
    def ensure_cloned(func: Callable[..., Any]) -> Callable[..., Any]:  # noqa: N805
        """Ensure that the GIT repo is cloned."""

        @functools.wraps(func)
        async def wrapper(self: "RepositoryManager", *args: Any, **kwargs: Any) -> Any:
            if not await self.is_cloned():
                raise NotClonedError(self.working_dir)
            return await func(self, *args, **kwargs)

        return wrapper

    async def is_installed(self) -> bool:
        """Return True if the GIT repo is installed."""
        if not await self.is_cloned():
            return False
        try:
            install_path = await self.get_install_path()
            return await self.hass.async_add_executor_job(install_path.exists)
        except (OSError, GPMError):
            return False

    @staticmethod
    def ensure_installed(func: Callable[..., Any]) -> Callable[..., Any]:  # noqa: N805
        """Ensure that the GIT repo is installed as a package."""

        @functools.wraps(func)
        async def wrapper(self: "RepositoryManager", *args: Any, **kwargs: Any) -> Any:
            if not await self.is_installed():
                raise NotInstalledError(self.slug)
            return await func(self, *args, **kwargs)

        return wrapper

    async def clone(self) -> None:
        """Clone the GIT repo."""
        if await self.is_cloned():
            raise AlreadyClonedError(self.working_dir)
        _LOGGER.info("Cloning %s to %s", self.repo_url, self.working_dir)
        try:
            self.__repo = await self.hass.async_add_executor_job(
                Repo.clone_from, self.repo_url, self.working_dir
            )
        except GitCommandError as e:
            raise CloneError(self.repo_url, self.working_dir) from e

    async def _get_latest_tag(self, only_stable: bool = True) -> str | None:
        """Return the semantiacally latest tag for the GIT repo.

        Given the list of tags, determine the latest version according to the semantic versioning.
        Invalid versions are always ignored.
        If `only_stable` is True, alpha, beta, dev, and RC versions are ignored.
        If no semantically valid versions are found, return None.
        """
        repo = await self._get_repo()
        tags = await self.hass.async_add_executor_job(lambda: map(str, repo.tags))
        versions: Iterable[AwesomeVersion] = filter(
            lambda v: v.valid, map(AwesomeVersion, tags)
        )
        if only_stable:
            versions = filter(
                lambda v: not (v.alpha or v.beta or v.dev or v.release_candidate),
                versions,
            )
        versions = sorted(versions, reverse=True)
        return str(versions[0]) if versions else None  # type: ignore[truthy-iterable]

    async def _get_latest_commit(self) -> str:
        """Return the latest commit hash."""
        repo = await self._get_repo()
        return await self.hass.async_add_executor_job(
            lambda: repo.heads[0].commit.hexsha
        )

    @ensure_cloned
    async def get_current_version(self) -> str:
        """Return the current version."""
        if not self._current_version_cache:
            repo = await self._get_repo()

            def _get_current_version() -> str:
                if self.update_strategy == UpdateStrategy.LATEST_COMMIT:
                    return repo.head.commit.hexsha
                return repo.git.describe("--tags", "--abbrev=0")

            self._current_version_cache = await self.hass.async_add_executor_job(
                _get_current_version
            )
        return self._current_version_cache

    @ensure_cloned
    async def get_latest_version(self) -> str:
        """Return the latest version."""
        if not self._latest_version_cache:
            latest_tag = None
            if self.update_strategy == UpdateStrategy.LATEST_TAG:
                latest_tag = await self._get_latest_tag()
            if self.update_strategy == UpdateStrategy.LATEST_UNSTABLE_TAG:
                latest_tag = await self._get_latest_tag(only_stable=False)
            self._latest_version_cache = (
                latest_tag if latest_tag else await self._get_latest_commit()
            )
        return self._latest_version_cache

    @ensure_cloned
    async def fetch(self) -> None:
        """Fetch the latest changes from the remote."""
        _LOGGER.info("Fetching %s", self.working_dir)
        self._latest_version_cache = None
        remote = await self._get_remote()
        await self.hass.async_add_executor_job(remote.fetch)

    async def _get_remote(self) -> Remote:
        """Return the remote of the GIT repo."""
        # this function exists mainly to be mocked in tests
        repo = await self._get_repo()
        return await self.hass.async_add_executor_job(lambda: repo.remotes[0])

    @ensure_cloned
    async def checkout(self, ref: str) -> None:
        """Checkout the specified reference."""
        _LOGGER.info("Checking out %s", ref)
        self._current_version_cache = None
        repo = await self._get_repo()
        try:
            await self.hass.async_add_executor_job(repo.git.checkout, ref)
        except GitCommandError as e:
            if "did not match any file(s) known to git" in e.stderr:
                raise CheckoutError(ref, "reference not found") from e
            raise CheckoutError(ref, e.stderr) from e

    @abstractmethod
    async def install(self) -> None:
        """Install the GIT repo."""
        if not await self.is_cloned():
            await self.clone()
            latest_version = await self.get_latest_version()
            await self.checkout(latest_version)

    @ensure_installed
    @abstractmethod
    async def update(self, version: str) -> None:
        """Update / downgrade the installed GIT repo."""
        _LOGGER.info("Updating to %s", version)
        current_version = await self.get_current_version()
        if current_version == version:
            raise VersionAlreadyInstalledError(version)

    @ensure_installed
    @abstractmethod
    async def uninstall(self) -> None:
        """Uninstall the GIT repo."""

    async def remove(self) -> None:
        """Remove the GIT repo."""
        if not await self.is_cloned():
            return
        if await self.is_installed():
            await self.uninstall()
        _LOGGER.info("Removing %s", self.working_dir)
        await self.hass.async_add_executor_job(shutil.rmtree, self.working_dir)
        self._current_version_cache = None
        self._latest_version_cache = None
        self.__repo = None

    @functools.cached_property
    def unique_id(self) -> str:
        """Return (reasonably) unique ID for the GIT repo.

        Examples:
            >>> rm = RepositoryManager(...)
            >>> rm.repo_url = 'https://github.com/user/foo.git'
            >>> rm.unique_id
            'github_com.user.foo'
            >>> rm.repo_url = 'https://github.com/another-user/bar'
            >>> rm.unique_id
            'github_com.another_user.bar'
            >>> rm.repo_url = 'https://gitlab.com/YETanotherUser123/baz/'
            >>> rm.unique_id
            'gitlab_com.yetanotheruser123.baz'

        """
        parsed_url = urlparse(self.repo_url)
        path_segments = parsed_url.path.strip("/").split("/")
        return ".".join(
            map(
                slugify,
                [
                    parsed_url.hostname,
                    *path_segments[:-1],
                    path_segments[-1].replace(".git", ""),
                ],
            )
        )

    @functools.cached_property
    def slug(self) -> str:
        """Return slug for the GIT repo."""
        return self.unique_id.rsplit(".", maxsplit=1)[-1]

    @ensure_cloned
    async def _get_repo(self) -> Repo:
        """Return the GIT repo."""
        if not self.__repo:
            self.__repo = await self.hass.async_add_executor_job(Repo, self.working_dir)
        return self.__repo

    @functools.cached_property
    def working_dir(self) -> Path:
        """Return the working directory of the GIT repo."""
        return self.clone_basedir / Path(self.unique_id)

    @ensure_cloned
    @abstractmethod
    async def get_install_path(self) -> Path:
        """Return the path to the installed repository."""

    @abstractmethod
    async def get_title(self) -> str:
        """Return the title of the repository."""


class IntegrationRepositoryManager(RepositoryManager):
    """Manage GIT repo as a HA integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        repo_url: str,
        update_strategy: UpdateStrategy,
    ) -> None:
        super().__init__(
            hass,
            repo_url,
            hass.config.path(PATH_CLONE_BASEDIR),
            hass.config.path(PATH_INTEGRATION_INSTALL_BASEDIR),
            update_strategy,
        )
        self._component_dir: Path | None = None

    async def install(self) -> None:
        """Install the GIT repo as a HA integration."""
        await super().install()
        component_dir = await self.get_component_dir()
        install_path = await self.get_install_path()
        _LOGGER.info("Installing %s to %s", component_dir, install_path)
        await self.hass.async_add_executor_job(
            lambda: install_path.parent.mkdir(parents=True, exist_ok=True)
        )
        try:
            await self.hass.async_add_executor_job(
                install_path.symlink_to, component_dir.resolve()
            )
        except FileExistsError:
            raise AlreadyInstalledError(install_path) from None
        await self._create_restart_issue("install")

    @RepositoryManager.ensure_installed
    async def update(self, version: str) -> None:
        """Update / downgrade the installed integration."""
        await super().update(version)
        await self.checkout(version)
        await self._create_restart_issue("update")

    @RepositoryManager.ensure_installed
    async def uninstall(self) -> None:
        """Uninstall the GIT repo."""
        install_path = await self.get_install_path()
        _LOGGER.info("Uninstalling %s", install_path)
        await self.hass.async_add_executor_job(install_path.unlink)
        await self._create_restart_issue("uninstall")

    @RepositoryManager.ensure_cloned
    async def get_component_dir(self) -> Path:
        """Return the directory of HA integration within the GIT repo."""
        if self._component_dir:
            return self._component_dir
        try:
            custom_components = await self.hass.async_add_executor_job(
                lambda: list(Path(self.working_dir / "custom_components").iterdir())
            )
        except FileNotFoundError:
            raise InvalidStructure(
                "No `custom_components` directory found", self.working_dir
            ) from None
        if len(custom_components) != 1:
            raise InvalidStructure(
                "Exactly one `custom_components` subdirectory is expected",
                self.working_dir,
            )
        self._component_dir = custom_components[0]
        return self._component_dir

    @RepositoryManager.ensure_cloned
    async def get_component_name(self) -> str:
        """Return the name of HA integration within the GIT repo."""
        return (await self.get_component_dir()).name

    @RepositoryManager.ensure_cloned
    async def get_install_path(self) -> Path:
        """Return the path to symlink which is used to install HA integration."""
        return self.install_basedir / await self.get_component_name()

    async def get_title(self) -> str:
        """Return the title of the repository."""
        return await self.get_component_name()

    async def _create_restart_issue(self, action: str) -> None:
        """Create an issue to inform the user that a restart is required."""
        component_name = await self.get_component_name()
        issue_data = {
            "action": action,
            "name": component_name,
        }
        async_create_issue(
            hass=self.hass,
            domain=DOMAIN,
            issue_id=f"restart_required.{component_name}",
            is_fixable=True,
            issue_domain=component_name,
            severity=IssueSeverity.WARNING,
            translation_key="restart_required",
            translation_placeholders=issue_data,
            data=issue_data,
        )


class ResourceRepositoryManager(RepositoryManager):
    """Manage GIT repo as a HA resource."""

    def __init__(
        self,
        hass: HomeAssistant,
        repo_url: str,
        update_strategy: UpdateStrategy,
    ) -> None:
        super().__init__(
            hass,
            repo_url,
            hass.config.path(PATH_CLONE_BASEDIR),
            hass.config.path(PATH_RESOURCE_INSTALL_BASEDIR),
            update_strategy,
        )
        self.hass = hass
        self._download_url: Template | None = None

    async def is_installed(self) -> bool:
        """Return True if the GIT repo is installed."""
        # check empty download_url to enable initial checkout
        if not await self.get_download_url():
            return False
        return await super().is_installed()

    async def install(self) -> None:
        """Install the GIT repo as a HA resource."""
        await super().install()
        await self._download_resource()
        resource_url = await self.get_resource_url()
        _LOGGER.info("Installing %s", resource_url)
        await self._add_resource(resource_url)
        await self._refresh_frontend()

    @RepositoryManager.ensure_installed
    async def uninstall(self) -> None:
        """Uninstall the GIT repo."""
        resource_url = await self.get_resource_url()
        install_path = await self.get_install_path()
        _LOGGER.info("Uninstalling resource %s, path %s", resource_url, install_path)
        await self._remove_resource(resource_url)
        await self.hass.async_add_executor_job(install_path.unlink)
        await self._refresh_frontend()

    @RepositoryManager.ensure_installed
    async def update(self, version: str):
        """Update / downgrade the installed resource."""
        await super().update(version)
        old_resource_url = await self.get_resource_url()
        old_install_path = await self.get_install_path()
        # checkout first - in case it fails, we don't want to remove the resource
        await self.checkout(version)
        await self.hass.async_add_executor_job(old_install_path.unlink)
        await self._download_resource()
        new_resource_url = await self.get_resource_url()
        await self._update_resource(old_resource_url, new_resource_url)
        await self._refresh_frontend()

    async def _download_resource(self):
        download_url = await self.get_download_url()
        install_path = await self.get_install_path()
        _LOGGER.info("Downloading %s to %s", download_url, install_path)
        await self.hass.async_add_executor_job(
            lambda: install_path.parent.mkdir(parents=True, exist_ok=True)
        )
        try:
            await async_download(self.hass, download_url, install_path)
        except (ClientError, OSError) as e:
            raise ResourceInstallError from e

    @classmethod
    async def _get_resource_storage(
        cls, hass: HomeAssistant
    ) -> ResourceStorageCollection:
        """Return the Lovelace resource storage."""
        try:
            res: ResourceStorageCollection = hass.data[LOVELACE_DOMAIN]["resources"]
        except KeyError as e:
            raise ResourcesUpdateError("ResourceStorageCollection not found") from e
        if not hasattr(res, "store") or res.store is None:
            raise ResourcesUpdateError("YAML mode detected")
        if res.store.key != "lovelace_resources" or res.store.version != 1:
            raise ResourcesUpdateError("Unexpected structure")
        if not res.loaded:
            await res.async_load()
        return res

    async def _add_resource(self, resource_url: str) -> None:
        _LOGGER.info("Adding resource %s", resource_url)
        resources = await self._get_resource_storage(self.hass)
        await resources.async_create_item({"res_type": "module", "url": resource_url})

    async def _update_resource(
        self, old_resource_url: str, new_resource_url: str
    ) -> None:
        _LOGGER.info("Updating resource %s to %s", old_resource_url, new_resource_url)
        resources = await self._get_resource_storage(self.hass)
        for entry in resources.async_items():
            if entry["url"] == old_resource_url:
                await resources.async_update_item(
                    entry["id"], {"url": new_resource_url}
                )
                break
        else:
            _LOGGER.warning("Resource %s not found", old_resource_url)
            await self._add_resource(new_resource_url)

    async def _remove_resource(self, resource_url) -> None:
        _LOGGER.info("Removing resource %s", resource_url)
        resources = await self._get_resource_storage(self.hass)
        for entry in resources.async_items():
            if entry["url"] == resource_url:
                await resources.async_delete_item(entry["id"])
                break
        else:
            _LOGGER.warning("Resource %s not found", resource_url)

    async def _refresh_frontend(self) -> None:
        """Refresh the frontend to apply the changes."""
        self.hass.bus.async_fire(EVENT_LOVELACE_UPDATED, {"url_path": None})

    @RepositoryManager.ensure_cloned
    async def get_download_url(self) -> str | None:
        """Return the download URL of the resource."""
        if not self._download_url:
            return None
        return self._download_url.async_render(version=await self.get_current_version())

    def set_download_url(self, value: str | Template | None) -> None:
        """Set the download URL of the resource."""
        if not value:
            self._download_url = None
            return
        if isinstance(value, Template):
            self._download_url = value
            return
        self._download_url = Template(value, self.hass)

    async def get_resource_name(self) -> Path:
        """Return the name of the resource."""
        download_url = await self.get_download_url()
        basename = Path(download_url.rsplit("/", maxsplit=1)[-1])
        current_version = slugify(await self.get_current_version())
        return Path(f"{basename.stem}_{current_version}{basename.suffix}")

    async def get_resource_url(self) -> str:
        """Return the URL of the installed resource."""
        resource_name = await self.get_resource_name()
        return f"{URL_BASE}/{resource_name}"

    async def get_install_path(self) -> Path:
        """Return the path to the installed resource."""
        resource_name = await self.get_resource_name()
        return self.install_basedir / resource_name

    async def get_title(self) -> str:
        """Return the title of the repository."""
        return self.slug


class GPMError(Exception):
    """Base class for GPM errors."""


class NotClonedError(GPMError):
    """Raised when the GIT repo is not cloned."""

    def __init__(self, working_dir: Path) -> None:
        self.working_dir = working_dir

    def __str__(self) -> str:
        return f"`{self.working_dir}` does not contain a GIT repository"


class InvalidStructure(GPMError):
    """Raised when the GIT repo has invalid structure."""

    def __init__(self, message: str, working_dir: Path) -> None:
        self.message = message
        self.working_dir = working_dir

    def __str__(self) -> str:
        return f"{self.message} in `{self.working_dir}`"


class AlreadyClonedError(GPMError):
    """Raised when the GIT repo is already cloned."""

    def __init__(self, working_dir: Path) -> None:
        self.working_dir = working_dir

    def __str__(self) -> str:
        return f"`{self.working_dir}` already contains a GIT repository"


class CloneError(GPMError):
    """Raised when the GIT repo cannot be cloned."""

    def __init__(self, repo_url: str, working_dir: Path) -> None:
        self.repo_url = repo_url
        self.working_dir = working_dir

    def __str__(self) -> str:
        return f"Cannot clone `{self.repo_url}` to `{self.working_dir}`"


class NotInstalledError(GPMError):
    """Raised when the GIT repo is not installed."""

    def __init__(self, slug: str) -> None:
        self.slug = slug

    def __str__(self) -> str:
        return f"`{self.slug}` is not installed"


class AlreadyInstalledError(GPMError):
    """Raised when the GIT repo is already installed."""

    def __init__(self, install_path: Path) -> None:
        self.install_path = install_path

    def __str__(self) -> str:
        return f"`{self.install_path}` already exists"


class CheckoutError(GPMError):
    """Raised when checkout of the GIT repo fails."""

    def __init__(self, ref: str, reason: str) -> None:
        self.ref = ref
        self.reason = reason

    def __str__(self) -> str:
        return f"Cannot check out `{self.ref}`: {self.reason}"


class VersionAlreadyInstalledError(GPMError):
    """Raised during update when the version is already installed."""

    def __init__(self, version: str) -> None:
        self.version = version

    def __str__(self) -> str:
        return f"`{self.version}` is already installed"


class ResourceInstallError(GPMError):
    """Raised when Lovelace resources can not be installed."""


class ResourcesUpdateError(GPMError):
    """Raised when Lovelace resources can not be updated."""

    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return f"Cannot update resources: {self.message}"


@contextlib.asynccontextmanager
async def async_open(
    hass: HomeAssistant, path: Path, *args, **kwargs
) -> AsyncGenerator:
    """Asynchronously open a file."""
    f = None
    try:
        f = await hass.async_add_executor_job(path.open, *args, **kwargs)  # type: ignore[arg-type]
        yield f
    finally:
        if f:
            f.close()


async def async_download(hass: HomeAssistant, url: str, path: Path) -> None:
    """Asynchronously download a file from URL to a local path."""
    # this functions exists mainly to be mocked in tests
    session = async_get_clientsession(hass)
    async with (
        session.get(url, raise_for_status=True) as response,
        async_open(hass, path, "wb") as file,
    ):
        # use larger chunks to prevent spawning too many jobs
        async for chunk in response.content.iter_chunked(DOWNLOAD_CHUNK_SIZE):
            await hass.async_add_executor_job(file.write, chunk)
