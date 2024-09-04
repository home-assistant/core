"""GitPython wrapper to manage GIT repos as HA integrations / resources.

When we speak about "version" in this file, we mean either a tag or a commit hash.
"""

from collections.abc import Callable, Iterable
from enum import StrEnum, auto
import functools
import logging
from pathlib import Path
import shutil
from typing import Any

from awesomeversion import AwesomeVersion
from git import GitCommandError, Repo

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
        url: str,
        type: RepositoryType,
        clone_basedir: Path | str,
        install_basedir: Path | str,
        update_strategy: UpdateStrategy = UpdateStrategy.LATEST_TAG,
    ) -> None:
        self.url = url
        self.type = type
        self.clone_basedir = Path(clone_basedir)
        self.install_basedir = Path(install_basedir)
        self.update_strategy = update_strategy
        self.__repo: Repo | None = None

    @property
    def is_cloned(self) -> bool:
        """Return True if the GIT repo is cloned."""
        try:
            return (self.working_dir / ".git").exists()
        except OSError:
            return False

    @staticmethod
    def ensure_cloned(func: Callable[..., Any]) -> Callable[..., Any]:  # noqa: N805
        """Ensure that the GIT repo is cloned."""

        @functools.wraps(func)
        def wrapper(self: "RepositoryManager", *args: Any, **kwargs: Any) -> Any:
            if not self.is_cloned:
                raise NotClonedError
            return func(self, *args, **kwargs)

        return wrapper

    @property
    def is_installed(self) -> bool:
        """Return True if the GIT repo is installed."""
        try:
            return self.install_symlink.exists()
        except OSError:
            return False

    @staticmethod
    def ensure_installed(func: Callable[..., Any]) -> Callable[..., Any]:  # noqa: N805
        """Ensure that the GIT repo is installed as a package."""

        @functools.wraps(func)
        def wrapper(self: "RepositoryManager", *args: Any, **kwargs: Any) -> Any:
            if not self.is_installed:
                raise NotInstalledError
            return func(self, *args, **kwargs)

        return wrapper

    def clone(self) -> None:
        """Clone the GIT repo."""
        if self.is_cloned:
            raise AlreadyClonedError(self.working_dir)
        _LOGGER.info("Cloning %s to %s", self.url, self.working_dir)
        try:
            self.__repo = Repo.clone_from(self.url, self.working_dir)
        except GitCommandError as e:
            raise CloneError(self.url, self.working_dir) from e

    def _get_latest_tag(self, only_stable: bool = True) -> str | None:
        """Return the semantiacally latest tag for the GIT repo.

        Given the list of tags, determine the latest version according to the semantic versioning.
        Invalid versions are always ignored.
        If `only_stable` is True, alpha, beta, dev, and RC versions are ignored.
        If no semantically valid versions are found, return None.
        """
        tags = map(str, self._repo.tags)
        versions: Iterable[AwesomeVersion] = map(AwesomeVersion, tags)
        versions = filter(lambda v: v.valid, versions)
        if only_stable:
            versions = filter(
                lambda v: not (v.alpha or v.beta or v.dev or v.release_candidate),
                versions,
            )
        versions = sorted(versions, reverse=True)
        return str(versions[0]) if versions else None

    def _get_latest_commit(self) -> str:
        """Return the latest commit hash."""
        return self._repo.heads[0].commit.hexsha

    @ensure_cloned
    def get_current_version(self) -> str:
        """Return the current version."""
        if self.update_strategy == UpdateStrategy.LATEST_COMMIT:
            return self._repo.head.commit.hexsha
        return self._repo.git.describe("--tags", "--abbrev=0")

    @ensure_cloned
    def get_latest_version(self) -> str:
        """Return the latest version."""
        latest_tag = None
        if self.update_strategy == UpdateStrategy.LATEST_TAG:
            latest_tag = self._get_latest_tag()
        if self.update_strategy == UpdateStrategy.LATEST_UNSTABLE_TAG:
            latest_tag = self._get_latest_tag(only_stable=False)
        return latest_tag if latest_tag else self._get_latest_commit()

    @ensure_cloned
    def fetch(self) -> None:
        """Fetch the latest changes from the remote."""
        _LOGGER.info("Fetching %s", self.working_dir)
        self._repo.remotes[0].fetch()

    @ensure_cloned
    def checkout(self, ref: str) -> None:
        """Checkout the specified reference."""
        _LOGGER.info("Checking out %s", ref)
        self._repo.git.checkout(ref)

    @ensure_cloned
    def install(self) -> None:
        """Install the GIT repo."""
        if self.type == RepositoryType.INTEGRATION:
            self._install_integration()
        elif self.type == RepositoryType.RESOURCE:
            raise NotImplementedError("Resource installation is not implemented yet.")

    def _install_integration(self) -> None:
        """Install the GIT repo as a HA integration."""
        _LOGGER.info("Installing %s to %s", self.component_dir, self.install_symlink)
        Path(self.install_symlink.parent).mkdir(parents=True, exist_ok=True)
        try:
            self.install_symlink.symlink_to(self.component_dir.resolve())
        except FileExistsError:
            raise AlreadyInstalledError(self.install_symlink) from None

    @ensure_installed
    def uninstall(self) -> None:
        """Uninstall the GIT repo."""
        _LOGGER.info("Uninstalling %s", self.install_symlink)
        self.install_symlink.unlink()

    @ensure_cloned
    def remove(self) -> None:
        """Remove the GIT repo."""
        if self.is_installed:
            self.uninstall()
        _LOGGER.info("Removing %s", self.working_dir)
        shutil.rmtree(self.working_dir)
        self.__repo = None

    @functools.cached_property
    def slug(self) -> str:
        """Return slug for the GIT repo.

        Examples:
            >>> rm = RepositoryManager(...)
            >>> rm.url = 'https://github.com/user/foo.git'
            >>> rm.slug
            'foo'
            >>> rm.url = 'https://github.com/user/bar'
            >>> rm.slug
            'bar'
            >>> rm.url = 'https://github.com/user/baz/'
            >>> rm.slug
            'baz'

        """
        return self.url.rstrip("/").split("/")[-1].replace(".git", "")

    @functools.cached_property
    @ensure_cloned
    def _repo(self) -> Repo:
        """Return the GIT repo."""
        self.__repo = Repo(self.working_dir)
        return self.__repo

    @functools.cached_property
    def working_dir(self) -> Path:
        """Return the working directory of the GIT repo."""
        return self.clone_basedir / Path(self.slug)

    @functools.cached_property
    @ensure_cloned
    def component_dir(self) -> Path:
        """Return the directory of HA integration within the GIT repo."""
        custom_components = list(Path(self.working_dir / "custom_components").iterdir())
        if len(custom_components) != 1:
            raise ValueError(
                "Exactly one `custom_components` subdirectory is expected."
            )
        return custom_components[0]

    @functools.cached_property
    def component_name(self) -> str:
        """Return the name of HA integration within the GIT repo."""
        return self.component_dir.name

    @functools.cached_property
    def install_symlink(self) -> Path:
        """Return the path to symlink which is used to install HA integration."""
        return self.install_basedir / self.component_name


class GPMError(Exception):
    """Base class for GPM errors."""


class NotClonedError(GPMError):
    """Raised when the GIT repo is not cloned."""


class AlreadyClonedError(GPMError):
    """Raised when the GIT repo is already cloned."""

    def __init__(self, working_dir: Path) -> None:
        self.working_dir = working_dir

    def __str__(self) -> str:
        return f"{self.working_dir} already contains a GIT repository"


class CloneError(GPMError):
    """Raised when the GIT repo cannot be cloned."""

    def __init__(self, url: str, working_dir: Path) -> None:
        self.url = url
        self.working_dir = working_dir

    def __str__(self) -> str:
        return f"Cannot clone {self.url} to {self.working_dir}"


class NotInstalledError(GPMError):
    """Raised when the GIT repo is not installed."""


class AlreadyInstalledError(GPMError):
    """Raised when the GIT repo is already installed."""

    def __init__(self, install_symlink: Path) -> None:
        self.install_symlink = install_symlink

    def __str__(self) -> str:
        return f"{self.install_symlink} already exists"
