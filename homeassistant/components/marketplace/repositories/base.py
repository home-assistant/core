"""Repository."""

from asyncio import Lock, sleep
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import partial
import io
import os
from pathlib import Path
import shutil
import tempfile
from typing import TYPE_CHECKING, Any, override
import zipfile

from aiogithubapi import (
    GitHubAuthenticationException,
    GitHubException,
    GitHubNotModifiedException,
    GitHubRatelimitException,
)
from aiogithubapi.models.git_tree import GitHubGitTreeEntryModel
import attr

from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, MAX_DOWNLOAD_SIZE, RELEASE_LIMIT
from ..enums import (
    DisabledReason,
    MarketplaceSignal,
    RepositoryCategory,
    RepositoryFile,
)
from ..exceptions import (
    CatalogContentUnresolvedError,
    GitHubAnonymousRateLimitError,
    GitHubRateLimitError,
    MarketplaceError,
    NotModifiedError,
    ReplacesBuiltInNotConfirmedError,
    RepositoryArchivedError,
    RepositoryExistsError,
)
from ..types import DownloadableContent
from ..utils.backup import Backup
from ..utils.decode import decode_content
from ..utils.decorator import concurrent, return_none_on_exception
from ..utils.file_system import (
    async_exists,
    async_lexists,
    async_remove,
    async_remove_directory,
)
from ..utils.filters import filter_content_return_one_of_type
from ..utils.json import json_loads_object
from ..utils.logger import LOGGER
from ..utils.path import entry_in_directory, is_safe, resolve_in_directory
from ..utils.queue_manager import QueueManager
from ..utils.storage import LEGACY_HACS_REPOSITORY_STORAGE_KEY, async_remove_storage
from ..utils.tree import (
    tree_entry_directory,
    tree_entry_filename,
    tree_entry_is_directory,
)
from ..utils.url import (
    github_archive,
    github_commit_archive,
    github_raw_file,
    github_release_asset,
    ref_version,
)
from ..utils.validate import Validate
from ..utils.version import (
    version_left_higher_or_equal_then_right,
    version_left_higher_then_right,
)

if TYPE_CHECKING:
    from aiogithubapi.models.release import GitHubReleaseAssetModel, GitHubReleaseModel
    from aiogithubapi.models.repository import GitHubRepositoryModel

    from ..base import MarketplaceManager


README_FILENAMES = (
    "README.md",
    "readme.md",
    "readme.MD",
    "README.MD",
    "README",
    "readme",
)

TOPIC_FILTER = (
    "add-on",
    "addon",
    "app",
    "custom-card",
    "custom-cards",
    "custom-component",
    "custom-components",
    "customcomponents",
    "hacktoberfest",
    "hacs-default",
    "hacs-integration",
    "hacs-repository",
    "hacs",
    "hass",
    "hassio",
    "home-assistant-custom",
    "home-assistant-frontend",
    "home-assistant-hacs",
    "home-assistant-sensor",
    "home-assistant",
    "home-automation",
    "homeassistant-components",
    "homeassistant-integration",
    "homeassistant-sensor",
    "homeassistant",
    "homeautomation",
    "integration",
    "lovelace-ui",
    "lovelace",
    "media-player",
    "mediaplayer",
    "plugin",
    "python_script",
    "python-script",
    "python",
    "sensor",
    "smart-home",
    "smarthome",
    "template",
    "templates",
    "theme",
    "themes",
)


REPOSITORY_KEYS_TO_EXPORT: tuple[tuple[str, Any], ...] = (
    # Keys can not be removed from this list until v3
    # If keys are added, the action need to be re-run with force
    ("description", ""),
    ("downloads", 0),
    ("domain", None),
    ("etag_releases", None),
    ("etag_repository", None),
    ("full_name", ""),
    ("last_commit", None),
    ("last_updated", 0),
    ("last_version", None),
    ("manifest_name", None),
    ("open_issues", 0),
    ("prerelease", None),
    ("stargazers_count", 0),
    ("topics", []),
)

REPOSITORY_MANIFEST_KEYS_TO_EXPORT: tuple[tuple[str, Any], ...] = (
    # If keys are added, the action need to be re-run with force
    ("name", None),
)


def _path_below(path: str, directory: str | None) -> str | None:
    """Return the path relative to the directory, None when it is not below it."""
    if not (directory := (directory or "").strip("/")):
        return path
    if not path.startswith(f"{directory}/"):
        return None
    return path[len(directory) + 1 :]


def _remove_written_content(marketplace: MarketplaceManager, path: str) -> None:
    """Remove what a failed first install wrote, this does I/O."""
    if not os.path.lexists(path) or not is_safe(marketplace, path):
        return

    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def _check_archive_size(archive: zipfile.ZipFile) -> None:
    """Reject an archive that expands to more than we are willing to write."""
    size = sum(info.file_size for info in archive.infolist())
    if size > MAX_DOWNLOAD_SIZE:
        raise MarketplaceError(
            f"The archive expands to {size} bytes, "
            f"the limit is {MAX_DOWNLOAD_SIZE} bytes"
        )


class FileInformation:
    """FileInformation."""

    def __init__(self, url: str, path: str, name: str) -> None:
        """Initialize the file information."""
        self.download_url = url
        self.path = path
        self.name = name


class RepositoryArchive:
    """The ZIP archive of a repository, as GitHub serves it for a ref.

    GitHub puts everything below a single top level directory named after
    the repository and the ref, the paths here leave it out.
    """

    def __init__(self, content: bytes) -> None:
        """Read the archive, this does I/O and has to run in the executor."""
        self._content = content
        self.members: dict[str, zipfile.ZipInfo] = {}

        with self._open() as archive:
            _check_archive_size(archive)
            for member in archive.infolist():
                if path := "/".join(member.filename.split("/")[1:]).rstrip("/"):
                    self.members[path] = member

    def _open(self) -> zipfile.ZipFile:
        """Open the archive."""
        try:
            return zipfile.ZipFile(io.BytesIO(self._content))
        except zipfile.BadZipFile as exception:
            raise MarketplaceError(f"Not a ZIP archive: {exception}") from exception

    @property
    def tree(self) -> list[GitHubGitTreeEntryModel]:
        """Return the members as the entries of a repository tree.

        Archives can leave out the entries of directories, so those are
        derived from the paths, in the order GitHub lists the tree.
        """
        entries: dict[str, bool] = {}
        for path, member in self.members.items():
            parts = path.split("/")
            for depth in range(1, len(parts)):
                entries.setdefault("/".join(parts[:depth]), True)
            entries.setdefault(path, member.is_dir())

        return [
            GitHubGitTreeEntryModel(
                {"path": path, "type": "tree" if is_directory else "blob"}
            )
            for path, is_directory in entries.items()
        ]

    def read(self, path: str) -> bytes:
        """Return the content of a file in the archive."""
        with self._open() as archive:
            return archive.read(self.members[path])

    def extract_directory(self, remote: str, local: str) -> None:
        """Extract everything below remote into local."""
        with self._open() as archive:
            extractable = []
            for path in archive.filelist:
                filename = "/".join(path.filename.split("/")[1:])
                # Blank names are the directory itself, not something to extract
                if not (relative := _path_below(filename, remote)):
                    continue
                path.filename = relative
                resolve_in_directory(local, path.filename)
                extractable.append(path)

            if len(extractable) == 0:
                raise MarketplaceError("No content to extract")
            archive.extractall(local, extractable)


@attr.s(auto_attribs=True)
class RepositoryData:
    """RepositoryData class."""

    archived: bool = False
    authors: list[str] = attr.field(factory=list)
    category: str = ""
    config_flow: bool = False
    default_branch: str | None = None
    description: str = ""
    domain: str | None = None
    # The folder a card was installed to, a rename on GitHub does not move it
    directory: str | None = None
    downloads: int = 0
    etag_repository: str | None = None
    etag_releases: str | None = None
    file_name: str = ""
    full_name: str = ""
    hide: bool = False
    has_issues: bool = True
    id: str | int = 0
    installed_commit: str | None = None
    installed_version: str | None = None
    installed: bool = False
    last_commit: str | None = None
    last_fetched: datetime | None = None
    last_updated: str | int = 0
    last_version: str | None = None
    manifest_name: str | None = None
    new: bool = True
    open_issues: int = 0
    prerelease: str | None = None
    published_tags: list[str] = attr.field(factory=list)
    releases: bool = False
    selected_tag: str | None = None
    show_beta: bool = False
    stargazers_count: int = 0
    topics: list[str] = attr.field(factory=list)

    @property
    def name(self) -> str | None:
        """Return the name."""
        if self.category == "integration":
            return self.domain
        return self.full_name.rsplit("/", maxsplit=1)[-1]

    @property
    def full_name_lower(self) -> str:
        """Return the name the repository is looked up by."""
        return self.full_name.lower()

    def to_json(self) -> dict[str, Any]:
        """Export to json."""
        return attr.asdict(self, filter=lambda attr, value: attr.name != "last_fetched")

    @staticmethod
    def create_from_dict(source: dict[str, Any]) -> RepositoryData:
        """Set attributes from dicts."""
        data = RepositoryData()
        data.update_data(source)
        return data

    def update_data(self, data: dict[str, Any]) -> None:
        """Update data of the repository."""
        for key, value in data.items():
            if key not in self.__dict__:
                continue

            if key == "last_fetched" and isinstance(value, (int, float)):
                setattr(self, key, datetime.fromtimestamp(value, UTC))
            elif key == "id":
                setattr(self, key, str(value))
            elif key == "topics":
                setattr(
                    self, key, [topic for topic in value if topic not in TOPIC_FILTER]
                )

            else:
                setattr(self, key, value)


@attr.s(auto_attribs=True)
class RepositoryManifest:
    """The repository manifest, parsed from hacs.json."""

    content_in_root: bool = False
    filename: str | None = None
    hacs: str | None = None  # Minimum HACS version, the `hacs` key of hacs.json
    hide_default_branch: bool = False
    homeassistant: str | None = None  # Minimum Home Assistant version
    manifest: dict[str, Any] = attr.field(factory=dict)
    name: str | None = None
    persistent_directory: str | None = None
    zip_release: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Export to json."""
        return attr.asdict(self)

    @staticmethod
    def from_dict(manifest: dict[str, Any] | None) -> RepositoryManifest:
        """Set attributes from dicts."""
        if manifest is None:
            raise MarketplaceError("Missing manifest data")

        manifest_data = RepositoryManifest()
        manifest_data.manifest = {
            k: v
            for k, v in manifest.items()
            if k in manifest_data.__dict__ and v != getattr(manifest_data, k)
        }

        for key, value in manifest_data.manifest.items():
            setattr(manifest_data, key, value)
        return manifest_data

    def update_data(self, data: dict[str, Any]) -> None:
        """Update the manifest data."""
        for key, value in data.items():
            if key not in self.__dict__:
                continue

            setattr(self, key, value)


class RepositoryReleases:
    """RepositoyReleases."""

    objects: list[GitHubReleaseModel] = []


class RepositoryPath:
    """RepositoryPath."""

    local: str = ""
    remote: str | None = None


class RepositoryContent:
    """RepositoryContent."""

    path: RepositoryPath
    single: bool = False


class Repository:
    """A repository the Marketplace knows about."""

    # Where the content of a category lives before the repository tree says
    # otherwise, and whether it is a single file
    remote_path: str | None = None
    single_file: bool = False

    def __init__(self, marketplace: MarketplaceManager) -> None:
        """Initialize the repository."""
        self.marketplace = marketplace
        self.additional_info = ""
        self.data = RepositoryData()
        self.content = RepositoryContent()
        self.content.path = RepositoryPath()
        self.content.path.remote = self.remote_path
        self.content.single = self.single_file
        self.repository_object: GitHubRepositoryModel | None = None
        self.updated_info = False
        self.state: str | None = None
        self.force_branch = False
        self.integration_manifest: dict[str, Any] = {}
        self.repository_manifest = RepositoryManifest.from_dict({})
        self.validate = Validate()
        self.releases = RepositoryReleases()
        self.pending_restart = False
        self.tree: list[GitHubGitTreeEntryModel] = []
        # The ref the tree was fetched for, its files are downloaded from there
        self.tree_ref: str | None = None
        self.treefiles: list[str] = []
        self.ref: str | None = None
        self.logger = LOGGER
        # Two installs of one repository would write over each other's files
        self._install_lock = Lock()
        self._replace_built_in_confirmed = False

    @override
    def __str__(self) -> str:
        """Return a string representation of the repository."""
        return self.string

    @property
    def string(self) -> str:
        """Return a string representation of the repository."""
        return f"<{self.data.category.title()} {self.data.full_name}>"

    @property
    def display_name(self) -> str:
        """Return display name."""
        if self.repository_manifest.name is not None:
            return self.repository_manifest.name

        if self.data.category == "integration":
            if self.data.manifest_name is not None:
                return self.data.manifest_name
            if "name" in self.integration_manifest:
                return str(self.integration_manifest["name"])

        return (
            self.data.full_name.rsplit("/", maxsplit=1)[-1]
            .replace("-", " ")
            .replace("_", " ")
            .title()
        )

    @property
    def display_status(self) -> str:
        """Return display_status."""
        if self.data.new:
            status = "new"
        elif self.pending_restart:
            status = "pending-restart"
        elif self.pending_update:
            status = "pending-upgrade"
        elif self.data.installed:
            status = "installed"
        else:
            status = "default"
        return status

    @property
    def display_installed_version(self) -> str:
        """Return the installed version to display."""
        if self.data.installed_version is not None:
            installed = self.data.installed_version
        elif self.data.installed_commit is not None:
            installed = self.data.installed_commit
        else:
            installed = ""
        return str(installed)

    @property
    def display_available_version(self) -> str:
        """Return the available version to display."""
        if self.data.show_beta and self.data.prerelease is not None:
            available = self.data.prerelease
        elif self.data.last_version is not None:
            available = self.data.last_version
        elif self.data.last_commit is not None:
            available = self.data.last_commit
        else:
            available = ""
        return str(available)

    @property
    def display_version_or_commit(self) -> str:
        """Does the repositoriy use releases or commits?"""
        if self.data.releases:
            version_or_commit = "version"
        else:
            version_or_commit = "commit"
        return version_or_commit

    @property
    def pending_update(self) -> bool:
        """Return True if pending update."""
        if self.data.installed:
            if self.data.selected_tag is not None:
                if self.data.selected_tag == self.data.default_branch:
                    if self.data.installed_commit != self.data.last_commit:
                        return True
                    return False
            # A commit that happens to look like a version is still a commit
            if (
                self.display_version_or_commit == "version"
                and self.data.installed_version is not None
            ):
                if (
                    result := version_left_higher_then_right(
                        self.display_available_version,
                        self.display_installed_version,
                    )
                ) is not None:
                    return result
            if self.display_installed_version != self.display_available_version:
                return True

        return False

    @property
    def can_install(self) -> bool:
        """Return True if we can install."""
        if self.repository_manifest.homeassistant is not None:
            if self.data.releases:
                if not version_left_higher_or_equal_then_right(
                    self.marketplace.version.string,
                    self.repository_manifest.homeassistant,
                ):
                    return False
        return True

    @property
    def localpath(self) -> str:
        """Return localpath."""
        return ""

    @property
    def should_try_releases(self) -> bool:
        """Return a boolean indicating whether to download releases or not."""
        if self.repository_manifest.zip_release and self.repository_manifest.filename:
            if self.repository_manifest.filename.endswith(".zip"):
                if self.ref != self.data.default_branch:
                    return True
        if self.ref == self.data.default_branch:
            return False
        # A theme comes from its themes directory, the way the catalog installs it
        if self.data.category != "plugin":
            return False
        if not self.data.releases:
            return False
        return True

    async def validate_repository(self) -> bool:
        """Validate."""
        return False

    @concurrent(concurrenttasks=10)
    async def update_repository(
        self, ignore_issues: bool = False, force: bool = False
    ) -> None:
        """Update the repository."""

    async def common_validate(self, ignore_issues: bool = False) -> None:
        """Common validation steps of the repository."""
        self.validate.errors.clear()

        # Make sure the repository exist.
        self.logger.debug("%s Checking repository.", self.string)
        await self.common_update_data(ignore_issues=ignore_issues)

        # Get the content of hacs.json
        if RepositoryFile.REPOSITORY_MANIFEST in [
            tree_entry_filename(entry) for entry in self.tree
        ]:
            if manifest := await self.async_get_repository_manifest():
                self.repository_manifest = RepositoryManifest.from_dict(manifest)
                self.data.update_data(self.repository_manifest.to_dict())
        else:
            # Every install reads it, a repository without one can not be updated
            self.validate.errors.append(
                f"{self.data.full_name} has no {RepositoryFile.REPOSITORY_MANIFEST} "
                "in its root, the Marketplace needs one to install it"
            )

    async def common_registration(self) -> None:
        """Common registration steps of the repository."""
        # Attach repository
        if self.repository_object is None:
            try:
                (
                    self.repository_object,
                    etag,
                ) = await self.async_get_repository_object(
                    etag=None if self.data.installed else self.data.etag_repository,
                )
                self.data.update_data(self.repository_object.as_dict)
                self.data.etag_repository = etag
            except NotModifiedError:
                self.logger.debug(
                    "%s Did not update, content was not modified", self.string
                )
                return

        if self.repository_object:
            self.data.last_updated = self.repository_object.pushed_at or 0
            self.data.last_fetched = dt_util.utcnow()

    @concurrent(concurrenttasks=10)
    async def common_update(
        self,
        ignore_issues: bool = False,
        force: bool = False,
        skip_releases: bool = False,
    ) -> bool:
        """Common information update steps of the repository."""
        self.logger.debug("%s Getting repository information", self.string)

        # Attach repository
        current_etag = self.data.etag_repository
        try:
            await self.common_update_data(
                ignore_issues=ignore_issues,
                force=force,
                skip_releases=skip_releases,
            )
        except RepositoryExistsError:
            self.marketplace.repositories.rename(
                self,
                self.marketplace.common.renamed_repositories[self.data.full_name],
            )
            await self.common_update_data(ignore_issues=ignore_issues, force=force)

        except GitHubAnonymousRateLimitError:
            raise

        except MarketplaceError:
            if not ignore_issues and not force:
                return False

        if (
            not self.data.installed
            and (current_etag == self.data.etag_repository)
            and not force
        ):
            self.logger.debug(
                "%s Did not update, content was not modified", self.string
            )
            return False

        # Update last updated
        if self.repository_object:
            self.data.last_updated = self.repository_object.pushed_at or 0

            # Update last available commit
            await self.async_set_last_commits()

        # Get the content of hacs.json
        if RepositoryFile.REPOSITORY_MANIFEST in [
            tree_entry_filename(entry) for entry in self.tree
        ]:
            if manifest := await self.async_get_repository_manifest():
                self.repository_manifest = RepositoryManifest.from_dict(manifest)
                self.data.update_data(self.repository_manifest.to_dict())

        self.additional_info = await self.async_get_readme_contents()

        # Set last fetch attribute
        self.data.last_fetched = dt_util.utcnow()

        return True

    async def download_zip_files(self, validate: Validate) -> None:
        """Download ZIP archive from repository release."""
        filename = self.repository_manifest.filename or ""

        try:
            await self.async_download_zip_file(
                DownloadableContent(
                    name=filename,
                    url=github_release_asset(
                        repository=self.data.full_name,
                        version=ref_version(self.ref),
                        filename=filename,
                    ),
                ),
                validate,
            )
        except MarketplaceError:
            validate.errors.append(
                f"Download of {self.repository_manifest.filename} was not completed"
            )

    async def async_download_zip_file(
        self,
        content: DownloadableContent,
        validate: Validate,
    ) -> None:
        """Download ZIP archive from repository release."""
        filecontent = await self.marketplace.async_download_file(content["url"])
        if filecontent is None:
            validate.errors.append(f"Failed to download {content['url']}")
            return

        temp_dir = await self.marketplace.hass.async_add_executor_job(tempfile.mkdtemp)
        try:
            # A scratch file, deliberately not named after the remote manifest
            temp_file = Path(temp_dir, "archive.zip")
            if not await self.marketplace.async_save_file(str(temp_file), filecontent):
                validate.errors.append(f"[{content['name']}] was not downloaded")
                return

            def _extract_zip_file() -> None:
                with zipfile.ZipFile(temp_file, "r") as zip_file:
                    _check_archive_size(zip_file)
                    for member in zip_file.namelist():
                        resolve_in_directory(self.content.path.local, member)
                    zip_file.extractall(self.content.path.local)

            await self.marketplace.hass.async_add_executor_job(_extract_zip_file)
            self.logger.info(
                "%s Download of %s completed", self.string, content["name"]
            )
        except OSError, zipfile.BadZipFile:
            validate.errors.append("Download was not completed")
        finally:
            await self.marketplace.hass.async_add_executor_job(
                partial(shutil.rmtree, temp_dir, ignore_errors=True)
            )

    async def download_content(self, version: str | None = None) -> None:
        """Download the content of a directory."""
        contents: list[FileInformation] | None = None
        if not self.repository_manifest.zip_release and self._installs_a_directory():
            self.logger.info("%s Downloading repository archive", self.string)
            try:
                await self.download_repository_zip()
            except MarketplaceError:
                self.logger.exception(
                    "%s Downloading repository archive failed", self.string
                )
            else:
                return

        if self.repository_manifest.filename:
            self.logger.debug("%s %s", self.string, self.repository_manifest.filename)

        if self.content.path.remote == "release" and version is not None:
            contents = await self.release_contents(version)

        if not contents:
            contents = self.gather_files_to_download()

        await self._async_download_files(contents)

    async def _async_download_files(self, contents: list[FileInformation]) -> None:
        """Download the files of the repository content."""
        download_queue = QueueManager(hass=self.marketplace.hass)
        for content in self._wanted_contents(contents):
            download_queue.add(self.dowload_repository_content(content))

        await download_queue.execute()

    def _wanted_contents(
        self, contents: list[FileInformation]
    ) -> list[FileInformation]:
        """Return the files of the content that have to be written."""
        if not contents:
            raise MarketplaceError("No content to download")

        if (
            self.repository_manifest.content_in_root
            and self.repository_manifest.filename
        ):
            if not (
                wanted := [
                    content
                    for content in contents
                    if content.name == self.repository_manifest.filename
                ]
            ):
                raise MarketplaceError(
                    f"The content has no {self.repository_manifest.filename}"
                )
            return wanted

        return contents

    async def download_repository_zip(self) -> None:
        """Download the zip archive of the repository."""
        ref = ref_version(self.ref)

        if not ref:
            raise MarketplaceError("Missing required elements.")

        archive = await self._async_download_archive(ref)
        await self._async_extract_archive(archive)

    async def _async_download_archive(
        self, ref: str, *, commit: bool = False
    ) -> RepositoryArchive:
        """Download and open the zip archive of the repository at a ref."""
        if commit:
            filecontent = await self.marketplace.async_download_file(
                github_commit_archive(repository=self.data.full_name, commit=ref)
            )
        else:
            filecontent = await self.marketplace.async_download_file(
                github_archive(
                    repository=self.data.full_name, version=ref, variant="tags"
                ),
                nolog=True,
            )

            if filecontent is None:
                filecontent = await self.marketplace.async_download_file(
                    github_archive(
                        repository=self.data.full_name, version=ref, variant="heads"
                    ),
                )

        if filecontent is None:
            raise MarketplaceError(f"[{self}] Failed to download zipball")

        return await self.marketplace.hass.async_add_executor_job(
            RepositoryArchive, filecontent
        )

    async def _async_extract_archive(self, archive: RepositoryArchive) -> None:
        """Extract the remote directory of the content from the archive."""
        if (remote := self.content.path.remote) is None:
            raise MarketplaceError("Missing required elements.")

        await self.marketplace.hass.async_add_executor_job(
            archive.extract_directory, remote, self.content.path.local
        )
        self.logger.info(
            "%s Content was extracted to %s", self.string, self.content.path.local
        )

    async def async_get_repository_manifest(
        self, ref: str | None = None
    ) -> dict[str, Any] | None:
        """Get the content of the hacs.json file."""
        try:
            response = await self.marketplace.async_github_api_method(
                method=self.marketplace.githubapi.repos.contents.get,
                raise_exception=False,
                repository=self.data.full_name,
                path=RepositoryFile.REPOSITORY_MANIFEST,
                params={"ref": ref or self.version_to_install()},
            )
            if response:
                return json_loads_object(decode_content(response.data.content))
        except GitHubNotModifiedException, ValueError:
            pass
        return None

    async def async_get_readme_contents(self, *, version: str | None = None) -> str:
        """Get the content of the README, shown on the repository page."""
        readme_files = [
            filename for filename in README_FILENAMES if filename in self.treefiles
        ]

        if not readme_files:
            return ""

        return (
            await self.get_documentation(filename=readme_files[0], version=version)
            or ""
        )

    def remove(self) -> None:
        """Run remove tasks."""
        if self.marketplace.repositories.is_registered(repository_id=str(self.data.id)):
            self.logger.info("%s Starting removal", self.string)
            self.marketplace.repositories.unregister(self)

    async def uninstall(self) -> None:
        """Run uninstall tasks."""
        self.logger.info("%s Removing", self.string)
        if not await self.remove_local_directory():
            raise MarketplaceError(
                f"Could not remove {self.data.full_name}, see the log for details"
            )
        self.data.installed = False
        await self._async_post_uninstall()
        await async_remove_storage(
            self.marketplace.hass,
            LEGACY_HACS_REPOSITORY_STORAGE_KEY.format(repository_id=self.data.id),
        )

        self.data.installed_version = None
        self.data.installed_commit = None
        self.marketplace.async_dispatch(
            MarketplaceSignal.REPOSITORY,
            {
                "id": 1337,
                "action": "uninstall",
                "repository": self.data.full_name,
                "repository_id": self.data.id,
            },
        )

        await self.async_remove_entity_device()
        ir.async_delete_issue(self.marketplace.hass, DOMAIN, f"removed_{self.data.id}")

    async def remove_local_directory(self) -> bool:
        """Check the local directory."""

        local_path = self.content.path.local

        try:
            if self.data.category == "template":
                local_path = str(entry_in_directory(local_path, self.data.file_name))
            elif self.data.category == "integration":
                if not self.data.domain:
                    self.logger.error("%s Missing domain", self.string)
                    return False
                local_path = self.content.path.local

            # The folder is named by remote input, removal stays inside its category
            if (directory := self._category_directory()) is not None:
                local_path = str(entry_in_directory(directory, local_path))

            if await async_lexists(self.marketplace.hass, local_path):
                if not is_safe(self.marketplace, local_path):
                    self.logger.error(
                        "%s Path %s is blocked from removal", self.string, local_path
                    )
                    return False
                self.logger.debug("%s Removing %s", self.string, local_path)

                if self.data.category == "template":
                    await async_remove(self.marketplace.hass, local_path)
                else:
                    await async_remove_directory(self.marketplace.hass, local_path)

                while await async_lexists(self.marketplace.hass, local_path):
                    await sleep(1)
            else:
                self.logger.debug(
                    "%s Presumed local content path %s does not exist",
                    self.string,
                    local_path,
                )

        except (OSError, MarketplaceError) as exception:
            self.logger.error(
                "%s Removing %s failed with %s", self.string, local_path, exception
            )
            return False
        return True

    def _category_directory(self) -> str | None:
        """Return the folder the installs of this category are written to."""
        configuration = self.marketplace.configuration
        directories: dict[str, str] = {
            RepositoryCategory.INTEGRATION: "custom_components",
            RepositoryCategory.PLUGIN: configuration.plugin_path,
            RepositoryCategory.THEME: configuration.theme_path,
        }

        if (directory := directories.get(self.data.category)) is None:
            return None
        return f"{self.marketplace.core.config_path}/{directory}"

    async def async_pre_registration(self) -> None:
        """Run pre registration steps."""

    @concurrent(concurrenttasks=10)
    async def async_registration(self, ref: str | None = None) -> None:
        """Run registration steps."""
        await self.async_pre_registration()

        if ref is not None:
            self.data.selected_tag = ref
            self.ref = ref
            self.force_branch = True

        if not await self.validate_repository():
            return

        # Run common registration steps.
        await self.common_registration()

        # Set correct local path
        self.content.path.local = self.localpath

        # Run local post registration steps.
        await self.async_post_registration()

    async def async_post_registration(self) -> None:
        """Run post registration steps."""

    async def async_pre_install(self) -> None:
        """Run pre install steps."""

    async def _async_pre_install(self) -> None:
        """Run pre install steps."""
        self.logger.info("%s Running pre installation steps", self.string)
        # Checked here, the version being written decides the domain it takes
        if (
            not self.data.installed
            and not self._replace_built_in_confirmed
            and await self.async_replaces_built_in()
        ):
            raise ReplacesBuiltInNotConfirmedError(str(self.data.domain))
        await self.async_pre_install()
        self.logger.info("%s Pre installation steps completed", self.string)

    async def async_install(self, *, version: str | None = None, **_: Any) -> None:
        """Run install steps."""
        await self._async_run_install(
            partial(self._async_write_version, version=version)
        )

    async def _async_run_install(
        self, install_repository: Callable[[], Awaitable[None]]
    ) -> None:
        """Run the install steps around writing the content."""
        self.marketplace.async_dispatch(
            MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
            {"repository": self.data.full_name, "progress": 30},
        )
        self.logger.info("%s Running installation steps", self.string)
        await install_repository()
        self.marketplace.async_dispatch(
            MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
            {"repository": self.data.full_name, "progress": 90},
        )
        self.logger.info("%s Installation steps completed", self.string)
        await self._async_post_install()
        self.marketplace.async_dispatch(
            MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
            {"repository": self.data.full_name, "progress": False},
        )

    async def async_post_installation(self) -> None:
        """Run post install steps."""

    async def async_post_uninstall(self) -> None:
        """Run post uninstall steps."""

    async def async_replaces_built_in(self) -> bool:
        """Return if the install takes the place of a built-in integration."""
        return False

    async def _async_post_uninstall(self) -> None:
        """Run post uninstall steps."""
        await self.async_post_uninstall()

    async def _async_post_install(self) -> None:
        """Run post install steps."""
        self.logger.info("%s Running post installation steps", self.string)
        await self.async_post_installation()
        self.data.new = False
        self.marketplace.async_dispatch(
            MarketplaceSignal.REPOSITORY,
            {
                "id": 1337,
                "action": "install",
                "repository": self.data.full_name,
                "repository_id": self.data.id,
            },
        )

        # Installs also come from update entities and automations, not only the
        # panel, so the new state is stored here for all of them
        await self.marketplace.data.async_write()
        self.logger.info("%s Post installation steps completed", self.string)

    async def _async_write_version(
        self, *, version: str | None = None, **_: Any
    ) -> None:
        """Common installation steps of the repository."""
        force_update = version is None or (
            self.data.last_version is not None and version != self.data.last_version
        )
        await self.update_repository(force=force_update)
        if self.content.path.local is None:
            raise MarketplaceError("repository.content.path.local is None")
        self.validate.errors.clear()

        version_to_install = self._branch_for_newest_commit(
            version or self.version_to_install()
        )
        if version_to_install == self.data.default_branch:
            self.ref = version_to_install
        else:
            self.ref = f"tags/{version_to_install}"

        LOGGER.debug("%s Version to install: %s", self.string, version_to_install)
        await self._async_write_content(
            partial(self._async_download_version, version_to_install)
        )

        if self.validate.success:
            self.data.installed = True
            self.data.installed_commit = self.data.last_commit

            if version_to_install == self.data.default_branch:
                self.data.installed_version = None
            else:
                self.data.installed_version = version_to_install

    async def _async_download_version(self, version: str) -> None:
        """Download the content of a version through the repository tree."""
        if self.repository_manifest.zip_release and self.repository_manifest.filename:
            await self.download_zip_files(self.validate)
        else:
            await self.download_content(version)

    async def _async_write_content(
        self, download: Callable[[], Awaitable[None]]
    ) -> None:
        """Write the content, putting back what was there when it fails."""
        # Checked here, the version being written decides where it goes
        await self._async_pre_install()
        self.marketplace.async_dispatch(
            MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
            {"repository": self.data.full_name, "progress": 40},
        )

        persistent_directory = await self._async_back_up_persistent_directory()
        backup: Backup | None = None
        backup_path = self._backup_path()
        existed = (
            backup_path is not None
            and await self.marketplace.hass.async_add_executor_job(
                os.path.lexists, backup_path
            )
        )

        def _restore_backups() -> None:
            """Put back what the backups moved away."""
            if backup is not None:
                backup.restore()
                backup.cleanup()
            # A first install has no backup, what it wrote so far goes instead
            if backup_path is not None and not existed:
                _remove_written_content(self.marketplace, backup_path)
            if persistent_directory is not None:
                persistent_directory.restore()
                persistent_directory.cleanup()

        if backup_path is not None:
            content_backup = Backup(
                marketplace=self.marketplace, local_path=backup_path
            )
            try:
                await self.marketplace.hass.async_add_executor_job(
                    content_backup.create
                )
            except MarketplaceError:
                # Nothing was written yet, only the persistent directory goes back
                await self.marketplace.hass.async_add_executor_job(_restore_backups)
                raise
            backup = content_backup

        LOGGER.debug("%s Local path is set to %s", self.string, self.content.path.local)
        LOGGER.debug(
            "%s Remote path is set to %s", self.string, self.content.path.remote
        )

        self.marketplace.async_dispatch(
            MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
            {"repository": self.data.full_name, "progress": 50},
        )

        try:
            await download()
            self.marketplace.async_dispatch(
                MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
                {"repository": self.data.full_name, "progress": 70},
            )
            self._raise_for_install_errors()
            await self.async_check_written_content()

            # Into the new content, while the old one can still come back
            if persistent_directory is not None:
                await self.marketplace.hass.async_add_executor_job(
                    persistent_directory.restore
                )
        except Exception as exception:
            # Whatever broke the install, the content that was there goes back
            await self.marketplace.hass.async_add_executor_job(_restore_backups)
            if isinstance(exception, OSError):
                raise MarketplaceError(
                    f"Could not write the downloaded content: {exception}"
                ) from exception
            raise

        self.marketplace.async_dispatch(
            MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
            {"repository": self.data.full_name, "progress": 80},
        )

        if backup is not None:
            await self.marketplace.hass.async_add_executor_job(backup.cleanup)

        if persistent_directory is not None:
            await self.marketplace.hass.async_add_executor_job(
                persistent_directory.cleanup
            )

    def _raise_for_install_errors(self) -> None:
        """Raise for the errors the install ran into, after logging them."""
        if not self.validate.errors:
            return

        for error in self.validate.errors:
            self.logger.error("%s %s", self.string, error)
        raise MarketplaceError("Could not install, see log for details")

    async def _async_back_up_persistent_directory(self) -> Backup | None:
        """Move the directory hacs.json keeps across updates out of the way."""
        if not self.repository_manifest.persistent_directory:
            return None

        local_path = Path(self.content.path.local).resolve()
        persistent_path = resolve_in_directory(
            local_path, self.repository_manifest.persistent_directory
        )
        # Keeping all of the installed content would put the old version back over the new
        if persistent_path == local_path:
            raise MarketplaceError(
                "The persistent_directory of hacs.json has to be a directory"
                " inside the installed content"
            )

        if not await async_exists(self.marketplace.hass, persistent_path):
            return None

        persistent_directory = Backup(
            marketplace=self.marketplace, local_path=persistent_path
        )
        await self.marketplace.hass.async_add_executor_job(persistent_directory.create)
        return persistent_directory

    def _backup_path(self) -> str | None:
        """Return what the install replaces, and has to be backed up first."""
        return self.content.path.local

    def _installs_a_directory(self) -> bool:
        """Return if the content is a directory, instead of the named file."""
        return not self.data.file_name and self.content.path.remote is not None

    async def async_check_written_content(self) -> None:
        """Refuse content that would not work, before it replaces the old."""

    async def async_get_repository_object(
        self,
        etag: str | None = None,
    ) -> tuple[GitHubRepositoryModel, str | None]:
        """Return the repository and the etag of the response."""
        try:
            response = await self.marketplace.githubapi.repos.get(
                self.data.full_name, etag=etag
            )
        except GitHubNotModifiedException as exception:
            raise NotModifiedError(exception) from exception
        except GitHubRatelimitException as exception:
            if not self.marketplace.github_connected:
                raise GitHubAnonymousRateLimitError(exception) from exception
            raise MarketplaceError(exception) from exception
        except GitHubAuthenticationException as exception:
            # Like every other GitHub call, a token that stopped working asks
            # the user to connect again
            if self.marketplace.github_connected:
                self.marketplace.disable(DisabledReason.INVALID_TOKEN)
            raise MarketplaceError(exception) from exception
        except GitHubException as exception:
            raise MarketplaceError(exception) from exception

        return response.data, response.etag

    def update_filenames(self) -> None:
        """Get the filename to target."""

    async def get_tree(self, ref: str | None) -> list[GitHubGitTreeEntryModel] | None:
        """Return the repository tree."""
        try:
            response = await self.marketplace.async_github_api_method(
                method=self.marketplace.githubapi.repos.git.get_tree,
                repository=self.data.full_name,
                tree_sha=ref,
                params={"recursive": "true"},
            )
        except GitHubException as exception:
            raise MarketplaceError(exception) from exception
        tree: list[GitHubGitTreeEntryModel] = response.data.tree
        return tree

    async def get_releases(
        self, prerelease: bool = False, returnlimit: int = RELEASE_LIMIT
    ) -> list[GitHubReleaseModel]:
        """Return the repository releases."""
        response = await self.marketplace.async_github_api_method(
            method=self.marketplace.githubapi.repos.releases.list,
            repository=self.data.full_name,
        )
        releases: list[GitHubReleaseModel] = []
        for release in response.data or []:
            if len(releases) == returnlimit:
                break
            if release.draft or (release.prerelease and not prerelease):
                continue
            releases.append(release)
        return releases

    async def common_update_data(  # noqa: C901
        self,
        ignore_issues: bool = False,
        force: bool = False,
        retry: bool = False,
        skip_releases: bool = False,
    ) -> None:
        """Common update data."""
        releases: list[GitHubReleaseModel] = []
        try:
            repository_object, etag = await self.async_get_repository_object(
                etag=None
                if force or self.data.installed
                else self.data.etag_repository,
            )
            self.repository_object = repository_object
            if self.data.full_name.lower() != repository_object.full_name.lower():
                self.marketplace.common.renamed_repositories[self.data.full_name] = (
                    repository_object.full_name
                )
                raise RepositoryExistsError  # noqa: TRY301 # handled below
            self.data.update_data(repository_object.as_dict)
            self.data.etag_repository = etag
        except NotModifiedError:
            return None
        except RepositoryExistsError:
            raise RepositoryExistsError from None
        except GitHubAnonymousRateLimitError:
            raise
        except MarketplaceError as exception:
            if not self.marketplace.status.startup:
                self.logger.error("%s %s", self.string, exception)
            if not ignore_issues:
                self.validate.errors.append("Repository does not exist.")
                raise MarketplaceError(exception) from exception

        # Make sure the repository is not archived.
        if self.data.archived and not ignore_issues:
            self.validate.errors.append("Repository is archived.")
            if self.data.full_name not in self.marketplace.common.archived_repositories:
                self.marketplace.common.archived_repositories.add(self.data.full_name)
            raise RepositoryArchivedError(f"{self} Repository is archived.")

        # Make sure the repository is not in the blacklist.
        if self.marketplace.repositories.is_removed(self.data.full_name):
            removed = self.marketplace.repositories.removed_repository(
                self.data.full_name
            )
            if removed.removal_type != "remove" and not ignore_issues:
                self.validate.errors.append(
                    "Repository has been requested to be removed."
                )
                raise MarketplaceError(
                    f"{self} Repository has been requested to be removed."
                )

        # Get releases.
        if not skip_releases:  # pylint: disable=too-many-nested-blocks
            try:
                releases = await self.get_releases(prerelease=True, returnlimit=30)
                if releases:
                    self.data.prerelease = None
                    for release in releases:
                        if release.draft:
                            continue
                        if release.prerelease:
                            if self.data.prerelease is None:
                                self.data.prerelease = release.tag_name
                        else:
                            self.data.last_version = release.tag_name
                            break

                    self.data.releases = True

                    filtered_releases = [
                        release
                        for release in releases
                        if not release.draft
                        and (self.data.show_beta or not release.prerelease)
                    ]
                    self.releases.objects = filtered_releases
                    self.data.published_tags = [x.tag_name for x in filtered_releases]

            except GitHubAnonymousRateLimitError:
                raise
            except GitHubRateLimitError:
                # Running out of requests says nothing about the releases, the
                # anonymous limit runs out on browsing alone.
                self.logger.debug("%s Rate limited, keeping the releases", self.string)
            except MarketplaceError:
                self.data.releases = False

        if not self.force_branch:
            self.ref = self.version_to_install()
        if self.data.releases:
            for release in self.releases.objects or []:
                if release.tag_name == self.ref:
                    if assets := release.assets:
                        if target_asset := self._find_target_asset(assets):
                            self.data.downloads = target_asset.download_count

        LOGGER.debug(
            "%s Running checks against %s",
            self.string,
            ref_version(self.ref),
        )

        try:
            tree = await self.get_tree(self.ref)
            if not tree:
                raise MarketplaceError("No files in tree")  # noqa: TRY301 # handled below
            self.tree = tree
            self.tree_ref = ref_version(self.ref)
            self.treefiles = [entry.path for entry in tree]
        except GitHubAnonymousRateLimitError:
            raise
        except MarketplaceError as exception:
            if (
                not retry
                and self.ref is not None
                and str(exception).startswith("GitHub returned 404")
            ):
                # Handle tags/branches being deleted.
                self.data.selected_tag = None
                self.ref = self.version_to_install()
                self.logger.warning(
                    "%s Selected version/branch %s has been removed, falling back to default",
                    self.string,
                    self.ref,
                )
                return await self.common_update_data(ignore_issues, force, True)
            if not self.marketplace.status.startup and not ignore_issues:
                self.logger.error("%s %s", self.string, exception)
            if not ignore_issues:
                raise MarketplaceError(exception) from None

    def gather_files_to_download(self) -> list[FileInformation]:
        """Return a list of file objects to be downloaded."""
        files: list[FileInformation] = []
        ref = ref_version(self.ref)
        releaseobjects = self.releases.objects

        if self.should_try_releases:
            for release in releaseobjects or []:
                if ref == release.tag_name:
                    files.extend(
                        FileInformation(
                            asset.browser_download_url, asset.name, asset.name
                        )
                        for asset in release.assets or []
                    )
            if files:
                return files

        return self.gather_tree_files_to_download()

    def gather_tree_files_to_download(self) -> list[FileInformation]:
        """Return the files of the repository tree to be downloaded."""
        files: list[FileInformation] = []
        tree = self.tree
        category = self.data.category
        remotelocation = self.content.path.remote

        if self.content.single:
            files.extend(
                self._tree_file_information(entry)
                for entry in tree
                if tree_entry_filename(entry) == self.data.file_name
            )
            return files

        if category == "plugin":
            for entry in tree:
                directory = tree_entry_directory(entry)
                filename = tree_entry_filename(entry)
                if directory in ["", "dist"]:
                    if remotelocation == "dist" and not filename.startswith("dist"):
                        continue
                    if not remotelocation:
                        if not filename.endswith(".js"):
                            continue
                        if directory != "":
                            continue
                    if not tree_entry_is_directory(entry):
                        files.append(self._tree_file_information(entry))
            if files:
                return files

        if self.repository_manifest.content_in_root:
            if not self.repository_manifest.filename:
                if category == "theme":
                    tree = filter_content_return_one_of_type(
                        self.tree, "", "yaml", "path"
                    )

        for entry in tree:
            if tree_entry_is_directory(entry):
                continue
            if _path_below(entry.path, self.content.path.remote) is not None:
                files.append(self._tree_file_information(entry))
        return files

    def _tree_file_information(self, entry: GitHubGitTreeEntryModel) -> FileInformation:
        """Return the download information of a file in the tree."""
        url = github_raw_file(
            repository=self.data.full_name, ref=self.tree_ref, path=entry.path
        )
        return FileInformation(url, entry.path, tree_entry_filename(entry))

    async def release_contents(
        self, version: str | None = None
    ) -> list[FileInformation] | None:
        """Gather the contents of a release."""
        release = await self.marketplace.async_github_api_method(
            method=self.marketplace.githubapi.generic,
            endpoint=f"/repos/{self.data.full_name}/releases/tags/{version}",
            raise_exception=False,
        )
        if release is None:
            return None

        assets = release.data.get("assets", [])

        # Every asset is downloaded, together they have to fit the download limit
        if sum(asset.get("size") or 0 for asset in assets) > MAX_DOWNLOAD_SIZE:
            raise MarketplaceError(
                f"The release assets of {version} are larger than the "
                f"{MAX_DOWNLOAD_SIZE} byte limit"
            )

        return [
            FileInformation(
                url=asset.get("browser_download_url"),
                path=asset.get("name"),
                name=asset.get("name"),
            )
            for asset in assets
        ]

    @concurrent(concurrenttasks=10)
    async def dowload_repository_content(self, content: FileInformation) -> None:
        """Download content."""
        self.logger.debug("%s Downloading %s", self.string, content.name)

        filecontent = await self.marketplace.async_download_file(content.download_url)

        if filecontent is None:
            self.validate.errors.append(f"[{content.name}] was not downloaded.")
            return

        await self._async_write_file(content, filecontent)

    async def _async_write_file(
        self, content: FileInformation, filecontent: bytes
    ) -> None:
        """Write a file of the content to where it belongs below the local path."""
        try:
            if self.content.single or content.path is None:
                local_directory = self.content.path.local

            else:
                _content_path = content.path
                if not self.repository_manifest.content_in_root and (
                    relative := _path_below(_content_path, self.content.path.remote)
                ):
                    _content_path = relative

                path_parts = f"{self.content.path.local}/{_content_path}".split("/")
                del path_parts[-1]
                local_directory = "/".join(path_parts)

            local_file_path = resolve_in_directory(
                self.content.path.local, f"{local_directory}/{content.name}"
            )

            result = await self.marketplace.async_save_file(
                str(local_file_path), filecontent
            )
            if result:
                self.logger.info(
                    "%s Download of %s completed", self.string, content.name
                )
                return
            self.validate.errors.append(f"[{content.name}] was not downloaded.")

        except (OSError, MarketplaceError) as exception:
            self.validate.errors.append(f"Download was not completed [{exception}]")

    async def async_remove_entity_device(self) -> None:
        """Remove the entity device."""
        if (config_entry := self.marketplace.configuration.config_entry) is None:
            return

        device_registry: dr.DeviceRegistry = dr.async_get(hass=self.marketplace.hass)
        identifier = (DOMAIN, str(self.data.id))

        # Looked up through our own config entry, since identifiers are only
        # guaranteed to be unique within a single config entry.
        for device in dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        ):
            if identifier in device.identifiers:
                device_registry.async_remove_device(device_id=device.id)
                return

    def version_to_install(self) -> str:
        """Determine which version to install."""
        if self.force_branch and self.ref is not None:
            return self.ref

        if self.data.last_version is not None:
            if self.data.selected_tag is not None:
                if self.data.selected_tag == self.data.last_version:
                    self.data.selected_tag = None
                    return self.data.last_version
                return self.data.selected_tag
            return self.data.last_version

        if self.data.selected_tag is not None:
            if self.data.selected_tag == self.data.default_branch:
                return self.data.default_branch
            if self.data.selected_tag in self.data.published_tags:
                return self.data.selected_tag

        return self.data.default_branch or "main"

    async def get_documentation(
        self,
        *,
        filename: str | None = None,
        version: str | None = None,
        **kwargs: Any,
    ) -> str | None:
        """Get the documentation of the repository."""
        if filename is None:
            return None

        target_version: str | None
        if version is not None:
            target_version = version
        elif self.data.installed:
            target_version = self.data.installed_version or self.data.installed_commit
        else:
            target_version = (
                self.data.last_version or self.data.last_commit or ref_version(self.ref)
            )

        self.logger.debug(
            "%s Getting documentation for version=%s,filename=%s",
            self.string,
            target_version,
            filename,
        )
        if target_version is None:
            return None

        result = await self.marketplace.async_download_file(
            f"https://raw.githubusercontent.com/{self.data.full_name}/{target_version}/{filename}",
            nolog=True,
        )

        return (
            result.decode(encoding="utf-8")
            .replace("<svg", "<disabled")
            .replace("</svg", "</disabled")
            if result
            else None
        )

    @return_none_on_exception
    async def get_repository_manifest(
        self, *, version: str | None, **kwargs: Any
    ) -> RepositoryManifest | None:
        """Get the hacs.json file of the repository."""
        if (result := await self.get_repository_manifest_raw(version=version)) is None:
            return None
        return RepositoryManifest.from_dict(result)

    @return_none_on_exception
    async def get_repository_manifest_raw(
        self,
        *,
        version: str | None,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Get the hacs.json file of the repository."""
        self.logger.debug("%s Getting hacs.json for version=%s", self.string, version)
        result = await self.marketplace.async_download_file(
            f"https://raw.githubusercontent.com/{self.data.full_name}/{version}/hacs.json",
            nolog=True,
            handle_rate_limit=True,
        )
        return json_loads_object(result) if result else None

    def _find_target_asset(
        self,
        assets: list[GitHubReleaseAssetModel] | None,
    ) -> GitHubReleaseAssetModel | None:
        """Find the correct asset for download."""
        if not assets:
            return None

        if self.data.file_name:
            for asset in assets:
                if asset.name == self.data.file_name:
                    return asset

        if self.data.category == "plugin":
            valid_filenames = (
                f"{self.data.name}.js",
                f"{self.data.name}-bundle.js",
                f"{self.data.name}.umd.js",
            )
            for asset in assets:
                if asset.name in valid_filenames:
                    return asset

        if target_filename := self.repository_manifest.filename:
            for asset in assets:
                if asset.name == target_filename:
                    return asset

        return assets[0] if assets else None

    def _branch_for_newest_commit(self, version: str) -> str:
        """Return the default branch when asked for the newest commit.

        Without releases a repository is updated to its newest commit, which is
        what the default branch holds. It is not a tag named after the commit.
        """
        if (
            self.data.last_version is None
            and self.data.default_branch
            and version == self.data.last_commit
        ):
            return self.data.default_branch
        return version

    async def _ensure_install_capabilities(
        self, ref: str | None, **kwargs: Any
    ) -> None:
        """Ensure that the install can be handled."""
        target_manifest: RepositoryManifest | None = None
        if ref is None:
            if not self.can_install:
                raise MarketplaceError(
                    f"This {self.data.category} is not available to install."
                )
            return

        if not ref:
            target_manifest = self.repository_manifest
        else:
            target_manifest = await self.get_repository_manifest(
                version=self._branch_for_newest_commit(ref)
            )

        if target_manifest is None:
            raise MarketplaceError(
                f"Version {ref} of {self.data.full_name} has no "
                f"{RepositoryFile.REPOSITORY_MANIFEST}, which installing needs"
            )

        self._check_minimum_version(target_manifest)

    def _check_minimum_version(self, manifest: RepositoryManifest) -> None:
        """Refuse a version that needs a newer Home Assistant."""
        # The `hacs` key in hacs.json names a version of the custom integration,
        # which cannot be compared with a Home Assistant version.
        if (
            manifest.homeassistant is not None
            and self.marketplace.version < manifest.homeassistant
        ):
            raise MarketplaceError(
                f"This version requires Home Assistant {manifest.homeassistant} or newer."
            )

    async def async_install_repository(
        self,
        *,
        ref: str | None = None,
        confirm_replace_built_in: bool = False,
        **_: Any,
    ) -> None:
        """Install a repository."""
        if self._install_lock.locked():
            raise MarketplaceError(f"{self.data.full_name} is already installing")

        async with self._install_lock:
            self._replace_built_in_confirmed = confirm_replace_built_in
            try:
                await self._async_install_repository(ref)
            finally:
                self._replace_built_in_confirmed = False

    async def async_wait_for_install(self) -> None:
        """Wait for an install of this repository that is running to finish."""
        if not self._install_lock.locked():
            return

        async with self._install_lock:
            return

    async def _async_install_repository(self, ref: str | None) -> None:
        """Install a repository, one install at a time."""
        if (catalog_version := self._catalog_version(ref)) is not None:
            try:
                await self._async_install_catalog_version(
                    catalog_version, requested=ref
                )
            except CatalogContentUnresolvedError as exception:
                self.logger.info(
                    "%s %s, installing through the GitHub API", self.string, exception
                )
            else:
                return

        await self._ensure_install_capabilities(ref)
        self.logger.info("Starting install, %s", ref)
        if self.display_version_or_commit == "version":
            self.marketplace.async_dispatch(
                MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
                {"repository": self.data.full_name, "progress": 10},
            )
            if not ref:
                await self.update_repository(force=True)
            else:
                self.ref = ref
            self.data.selected_tag = ref
            self.force_branch = ref is not None
            self.marketplace.async_dispatch(
                MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
                {"repository": self.data.full_name, "progress": 20},
            )

        try:
            await self.async_install(version=ref)
        except GitHubAnonymousRateLimitError, ReplacesBuiltInNotConfirmedError:
            raise
        except MarketplaceError as exception:
            raise MarketplaceError(
                f"Installing {self.data.full_name} with version {ref or self.data.last_version or self.data.last_commit} failed with ({exception})"
            ) from exception
        finally:
            self.data.selected_tag = None
            self.force_branch = False
            self.marketplace.async_dispatch(
                MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
                {"repository": self.data.full_name, "progress": False},
            )

    def _catalog_version(self, ref: str | None) -> str | None:
        """Return the catalog version to install without the GitHub API.

        Anonymous access to the API runs out after a handful of installs. The
        catalog already names the version, and the files come from hosts
        without that limit. A version the user picked keeps using the API.
        """
        if not self.marketplace.repositories.is_default(str(self.data.id)):
            return None

        catalog_version = self.data.last_version or self.data.last_commit
        requested = ref if ref is not None else self.data.selected_tag
        if requested is not None and requested != catalog_version:
            return None

        return catalog_version

    async def _async_install_catalog_version(
        self, version: str, *, requested: str | None
    ) -> None:
        """Install a version the catalog names, without the GitHub API."""
        if requested is None and not self.can_install:
            raise MarketplaceError(
                f"This {self.data.category} is not available to install."
            )

        # Without releases the catalog names the last commit instead
        commit = self.data.last_version is None
        self.logger.info("Starting install, %s", version)
        self.marketplace.async_dispatch(
            MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
            {"repository": self.data.full_name, "progress": 10},
        )

        try:
            download = await self._async_prepare_catalog_install(version, commit=commit)
            self.marketplace.async_dispatch(
                MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
                {"repository": self.data.full_name, "progress": 20},
            )

            try:
                await self._async_run_install(
                    partial(
                        self._async_write_catalog_version,
                        version,
                        download,
                        commit=commit,
                    )
                )
            except GitHubAnonymousRateLimitError, ReplacesBuiltInNotConfirmedError:
                raise
            except MarketplaceError as exception:
                raise MarketplaceError(
                    f"Installing {self.data.full_name} with version {version} failed with ({exception})"
                ) from exception
        finally:
            self.data.selected_tag = None
            self.force_branch = False
            self.marketplace.async_dispatch(
                MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
                {"repository": self.data.full_name, "progress": False},
            )

    async def _async_prepare_catalog_install(
        self, version: str, *, commit: bool
    ) -> Callable[[], Awaitable[None]]:
        """Work out what a catalog version writes, and return what writes it.

        Nothing is written here. When the content can not be resolved, the
        repository is left as the GitHub API path expects to find it.
        """
        self.validate.errors.clear()
        if (manifest := await self.get_repository_manifest(version=version)) is None:
            raise CatalogContentUnresolvedError(
                f"No readable {RepositoryFile.REPOSITORY_MANIFEST} in {version}"
            )

        self._check_minimum_version(manifest)

        previous_manifest = self.repository_manifest
        self.repository_manifest = manifest
        self.ref = version if commit else f"tags/{version}"
        self.content.path.remote = self.remote_path
        self.content.single = self.single_file

        try:
            return await self._async_resolve_catalog_content(version, commit=commit)
        except MarketplaceError:
            self.repository_manifest = previous_manifest
            self.content.path.remote = self.remote_path
            self.content.single = self.single_file
            raise

    async def _async_resolve_catalog_content(
        self, version: str, *, commit: bool
    ) -> Callable[[], Awaitable[None]]:
        """Resolve the content of a catalog version from the repository archive."""
        if self.repository_manifest.zip_release and self.repository_manifest.filename:
            raise CatalogContentUnresolvedError(
                f"A {self.data.category} can not use a ZIP release from the catalog"
            )

        archive = await self._async_open_catalog_archive(version, commit=commit)
        try:
            self.resolve_archive_content()
        except MarketplaceError as exception:
            # Files marked export-ignore are in the tree, but not in the archive
            raise CatalogContentUnresolvedError(str(exception)) from exception

        return partial(self._async_write_archive_content, archive)

    async def _async_open_catalog_archive(
        self, version: str, *, commit: bool
    ) -> RepositoryArchive:
        """Download the archive of a catalog version, its members make up the tree."""
        try:
            archive = await self._async_download_archive(version, commit=commit)
        except MarketplaceError as exception:
            raise CatalogContentUnresolvedError(str(exception)) from exception

        self.tree = archive.tree
        self.tree_ref = version
        self.treefiles = [entry.path for entry in self.tree]
        return archive

    def resolve_content(self) -> None:
        """Point the content at what the repository tree holds.

        Raises MarketplaceError when the tree holds nothing to install.
        """

    def resolve_archive_content(self) -> None:
        """Point the content at what the archive of a catalog version holds."""
        self.resolve_content()

    async def _async_write_archive_content(self, archive: RepositoryArchive) -> None:
        """Write the content of a catalog version from its archive."""
        if self._installs_a_directory():
            await self._async_extract_archive(archive)
            return

        for content in self._wanted_contents(self.gather_tree_files_to_download()):
            filecontent = await self.marketplace.hass.async_add_executor_job(
                archive.read, content.path
            )
            await self._async_write_file(content, filecontent)

    async def _async_write_catalog_version(
        self,
        version: str,
        download: Callable[[], Awaitable[None]],
        *,
        commit: bool,
    ) -> None:
        """Write the content of a catalog version and mark it installed."""
        await self._async_write_content(download)

        self.data.installed = True
        self.data.installed_commit = self.data.last_commit
        if commit:
            self.data.installed_version = None
        else:
            # The catalog only names a version for repositories with releases
            self.data.releases = True
            self.data.installed_version = version

    async def async_get_releases(self) -> list[GitHubReleaseModel]:
        """Get the last 30 releases of a repository."""
        response = await self.marketplace.async_github_api_method(
            method=self.marketplace.githubapi.repos.releases.list,
            repository=self.data.full_name,
            kwargs={"per_page": 30},
        )
        releases: list[GitHubReleaseModel] = response.data
        return releases

    async def async_set_last_commits(self) -> None:
        """Set the last commit for the repository."""
        response = await self.marketplace.async_github_api_method(
            method=self.marketplace.githubapi.generic,
            endpoint=f"/repos/{self.data.full_name}/branches/{self.data.default_branch}",
        )
        if response is not None and response.data:
            last_commit = response.data["commit"]["sha"]
            self.data.last_commit = last_commit[:7]
