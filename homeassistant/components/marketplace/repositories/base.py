"""Repository."""

import asyncio
from asyncio import Lock, sleep
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import partial
import io
import os
from pathlib import Path
import shutil
import tempfile
from typing import TYPE_CHECKING, Any, Literal, override
import zipfile

from aiogithubapi import (
    GitHubAuthenticationException,
    GitHubException,
    GitHubNotFoundException,
    GitHubNotModifiedException,
    GitHubRatelimitException,
)
from aiogithubapi.models.git_tree import GitHubGitTreeEntryModel
import attr
import probatio

from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads_object

from ..const import DOMAIN, MAX_ARCHIVE_MEMBERS, MAX_DOWNLOAD_SIZE, RELEASE_LIMIT
from ..enums import DisabledReason, MarketplaceSignal, RepositoryFile
from ..exceptions import (
    CatalogContentUnresolvedError,
    GitHubAnonymousRateLimitError,
    GitHubRateLimitError,
    MarketplaceError,
    NotModifiedError,
    ReplacesBuiltInNotConfirmedError,
    RepositoryArchivedError,
    RepositoryBusyError,
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
from ..utils.logger import LOGGER
from ..utils.path import entry_in_directory, is_safe, resolve_in_directory
from ..utils.queue_manager import QueueManager
from ..utils.tree import tree_entry_filename, tree_entry_is_directory
from ..utils.url import (
    github_archive,
    github_commit_archive,
    github_raw_file,
    github_release_asset,
    ref_version,
)
from ..utils.validate import REPOSITORY_MANIFEST_VALUES, Validate, is_valid_ref
from ..utils.version import is_newer_version, is_same_or_newer_version

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


# What a catalog entry leaves out is reset to these
REPOSITORY_KEYS_TO_EXPORT: tuple[tuple[str, Any], ...] = (
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

REPOSITORY_MANIFEST_KEYS_TO_EXPORT: tuple[tuple[str, Any], ...] = (("name", None),)


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
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise MarketplaceError(
            translation_domain=DOMAIN,
            translation_key="archive_too_many_files",
            translation_placeholders={
                "count": str(len(members)),
                "limit": str(MAX_ARCHIVE_MEMBERS),
            },
        )

    size = sum(info.file_size for info in members)
    if size > MAX_DOWNLOAD_SIZE:
        raise MarketplaceError(
            translation_domain=DOMAIN,
            translation_key="archive_too_large",
            translation_placeholders={
                "size": str(size),
                "limit": str(MAX_DOWNLOAD_SIZE),
            },
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
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="archive_not_zip",
                translation_placeholders={"error": str(exception)},
            ) from exception

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
                raise MarketplaceError(
                    translation_domain=DOMAIN, translation_key="archive_without_content"
                )
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
    # The folder a card or theme was installed to, a rename on GitHub does not move it
    directory: str | None = None
    downloads: int = 0
    etag_repository: str | None = None
    etag_releases: str | None = None
    file_name: str = ""
    full_name: str = ""
    hide: bool = False
    has_issues: bool = True
    # "0" until the repository is known on GitHub
    id: str = "0"
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
    hacs: str | None = None  # The `hacs` key of hacs.json, not compared
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
            raise MarketplaceError(
                translation_domain=DOMAIN, translation_key="repository_manifest_missing"
            )

        manifest_data = RepositoryManifest()
        manifest_data.manifest = {}
        for key, value in manifest.items():
            if (validator := REPOSITORY_MANIFEST_VALUES.get(key)) is None:
                continue
            try:
                validator(value)
            except probatio.Invalid:
                LOGGER.warning("Ignoring %s in hacs.json, %r is not valid", key, value)
                continue
            if value != getattr(manifest_data, key):
                manifest_data.manifest[key] = value

        for key, value in manifest_data.manifest.items():
            setattr(manifest_data, key, value)
        return manifest_data

    def update_data(self, data: dict[str, Any]) -> None:
        """Update the manifest data."""
        for key, value in data.items():
            if key not in self.__dict__:
                continue

            setattr(self, key, value)


@attr.s(auto_attribs=True)
class RepositoryReleases:
    """The releases of a repository, newest first."""

    objects: list[GitHubReleaseModel] = attr.field(factory=list)


@attr.s(auto_attribs=True)
class RepositoryPath:
    """Where the content is, in the repository and on disk."""

    local: str = ""
    remote: str | None = None


@attr.s(auto_attribs=True)
class RepositoryContent:
    """The content a repository installs."""

    path: RepositoryPath = attr.field(factory=RepositoryPath)
    single: bool = False


class Repository:
    """A repository the Marketplace knows about."""

    # Where the content of a category lives before the repository tree says
    # otherwise, and whether it is a single file
    remote_path: str | None = None
    single_file: bool = False
    # Only dashboard resources ship as release assets
    ships_release_assets: bool = False

    def __init__(self, marketplace: MarketplaceManager) -> None:
        """Initialize the repository."""
        self.marketplace = marketplace
        self.additional_info = ""
        self.data = RepositoryData()
        self.content = RepositoryContent(
            path=RepositoryPath(remote=self.remote_path), single=self.single_file
        )
        self.repository_object: GitHubRepositoryModel | None = None
        self.updated_info = False
        self.force_branch = False
        self.integration_manifest: dict[str, Any] = {}
        self.repository_manifest = RepositoryManifest.from_dict({})
        self.validate = Validate()
        self.releases = RepositoryReleases()
        self.pending_restart = False
        # The last request for the repository on GitHub could not reach it
        self.unreachable = False
        self.tree: list[GitHubGitTreeEntryModel] = []
        # The ref the tree was fetched for, its files are downloaded from there
        self.tree_ref: str | None = None
        self.treefiles: list[str] = []
        self.ref: str | None = None
        self.logger = LOGGER
        # Two installs of one repository would write over each other's files
        self._install_lock = Lock()
        # What the files downloaded one by one may still add up to
        self._download_budget = MAX_DOWNLOAD_SIZE
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

        if (content_name := self._content_name()) is not None:
            return content_name

        return (
            self.data.full_name.rsplit("/", maxsplit=1)[-1]
            .replace("-", " ")
            .replace("_", " ")
            .title()
        )

    def _content_name(self) -> str | None:
        """Return the name the installed content gives itself, if any."""
        return None

    @property
    def display_status(self) -> str:
        """Return the status the panel shows the repository with."""
        if self.data.new:
            return "new"
        if self.pending_restart:
            return "pending-restart"
        if self.pending_update:
            return "pending-upgrade"
        if self.data.installed:
            return "installed"
        return "default"

    @property
    def display_installed_version(self) -> str:
        """Return the installed version to display."""
        if self.data.installed_version is not None:
            return str(self.data.installed_version)
        if self.data.installed_commit is not None:
            return str(self.data.installed_commit)
        return ""

    @property
    def display_available_version(self) -> str:
        """Return the available version to display."""
        if self.data.show_beta and self.data.prerelease is not None:
            return str(self.data.prerelease)
        if self.data.last_version is not None:
            return str(self.data.last_version)
        if self.data.last_commit is not None:
            return str(self.data.last_commit)
        return ""

    @property
    def display_version_or_commit(self) -> str:
        """Return if the repository is installed by version or by commit."""
        return "version" if self.data.releases else "commit"

    @property
    def pending_update(self) -> bool:
        """Return if a newer version than the installed one is available."""
        if not self.data.installed:
            return False

        # Following the default branch, every new commit is an update
        if (
            self.data.selected_tag is not None
            and self.data.selected_tag == self.data.default_branch
        ):
            return self.data.installed_commit != self.data.last_commit

        # A commit that happens to look like a version is still a commit
        if (
            self.display_version_or_commit == "version"
            and self.data.installed_version is not None
            and (
                newer := is_newer_version(
                    self.display_available_version, self.display_installed_version
                )
            )
            is not None
        ):
            return newer

        return self.display_installed_version != self.display_available_version

    @property
    def can_install(self) -> bool:
        """Return if this Home Assistant is new enough for the repository."""
        if self.repository_manifest.homeassistant is None or not self.data.releases:
            return True

        return is_same_or_newer_version(
            self.marketplace.version.string, self.repository_manifest.homeassistant
        )

    @property
    def localpath(self) -> str:
        """Return localpath."""
        return ""

    @property
    def should_try_releases(self) -> bool:
        """Return if the content comes from the assets of a release."""
        if self.ref == self.data.default_branch:
            return False

        manifest = self.repository_manifest
        if manifest.zip_release and (manifest.filename or "").endswith(".zip"):
            return True

        return self.ships_release_assets and bool(self.data.releases)

    async def validate_repository(self) -> bool:
        """Check the repository has content this category installs."""
        await self.common_validate()
        self.resolve_content()
        await self.async_read_content_details()

        # Startup checks every repository, only a later check is worth a log line
        if not self.marketplace.status.startup:
            for error in self.validate.errors:
                self.logger.error("%s %s", self.string, error)
        return self.validate.success

    async def async_read_content_details(self) -> None:
        """Read what the resolved content tells about the repository."""

    @concurrent(concurrenttasks=10)
    async def update_repository(
        self, ignore_issues: bool = False, force: bool = False
    ) -> None:
        """Update the repository."""

    async def common_validate(self, ignore_issues: bool = False) -> None:
        """Common validation steps of the repository."""
        self.validate.errors.clear()

        self.logger.debug("%s Checking repository.", self.string)
        await self.common_update_data(ignore_issues=ignore_issues)

        if RepositoryFile.REPOSITORY_MANIFEST in [
            tree_entry_filename(entry) for entry in self.tree
        ]:
            if manifest := await self.async_get_repository_manifest():
                self.repository_manifest = RepositoryManifest.from_dict(manifest)
                self.data.update_data(self.repository_manifest.to_dict())
        else:
            # Every install reads it, a repository without one can not be updated
            self.validate.errors.append(
                MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="repository_manifest_not_in_root",
                    translation_placeholders={"repository": self.data.full_name},
                )
            )

    async def common_registration(self) -> None:
        """Common registration steps of the repository."""
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
        self, ignore_issues: bool = False, force: bool = False
    ) -> bool:
        """Common information update steps of the repository."""
        self.logger.debug("%s Getting repository information", self.string)

        current_etag = self.data.etag_repository
        try:
            await self.common_update_data(ignore_issues=ignore_issues, force=force)
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

        if self.repository_object:
            self.data.last_updated = self.repository_object.pushed_at or 0
            await self.async_set_last_commits()

        if RepositoryFile.REPOSITORY_MANIFEST in [
            tree_entry_filename(entry) for entry in self.tree
        ]:
            if manifest := await self.async_get_repository_manifest():
                self.repository_manifest = RepositoryManifest.from_dict(manifest)
                self.data.update_data(self.repository_manifest.to_dict())

        self.additional_info = await self.async_get_readme_contents()

        self.data.last_fetched = dt_util.utcnow()

        return True

    async def download_zip_files(self, validate: Validate) -> None:
        """Download the ZIP asset hacs.json names, and extract it."""
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
                MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="file_not_downloaded",
                    translation_placeholders={
                        "file": str(self.repository_manifest.filename)
                    },
                )
            )

    async def async_download_zip_file(
        self,
        content: DownloadableContent,
        validate: Validate,
    ) -> None:
        """Download a ZIP archive and extract it into the local path."""
        filecontent = await self.marketplace.async_download_file(content["url"])
        if filecontent is None:
            validate.errors.append(
                MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="file_not_downloaded",
                    translation_placeholders={"file": content["url"]},
                )
            )
            return

        temp_dir = await self.marketplace.hass.async_add_executor_job(tempfile.mkdtemp)
        try:
            # A scratch file, deliberately not named after the remote manifest
            temp_file = Path(temp_dir, "archive.zip")
            if not await self.marketplace.async_save_file(str(temp_file), filecontent):
                validate.errors.append(
                    MarketplaceError(
                        translation_domain=DOMAIN,
                        translation_key="file_not_downloaded",
                        translation_placeholders={"file": content["name"]},
                    )
                )
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
        except (OSError, zipfile.BadZipFile) as exception:
            validate.errors.append(
                MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="download_incomplete",
                    translation_placeholders={"error": str(exception)},
                )
            )
        finally:
            await self.marketplace.hass.async_add_executor_job(
                partial(shutil.rmtree, temp_dir, ignore_errors=True)
            )

    async def download_content(self, version: str | None = None) -> None:
        """Download the content, the archive first when it is a directory."""
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

        if self.content.path.remote == "release" and version is not None:
            contents = await self.release_contents(version)

        if not contents:
            contents = self.gather_files_to_download()

        await self._async_download_files(contents)

    async def _async_download_files(self, contents: list[FileInformation]) -> None:
        """Download the files of the repository content.

        It is also the way around an archive over the limits, so it has the
        same limits.
        """
        wanted = self._wanted_contents(contents)
        if len(wanted) > MAX_ARCHIVE_MEMBERS:
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="content_too_many_files",
                translation_placeholders={
                    "count": str(len(wanted)),
                    "limit": str(MAX_ARCHIVE_MEMBERS),
                },
            )

        self._download_budget = MAX_DOWNLOAD_SIZE
        download_queue = QueueManager(hass=self.marketplace.hass)
        for content in wanted:
            download_queue.add(self.download_repository_file(content))

        await download_queue.execute()

    def _wanted_contents(
        self, contents: list[FileInformation]
    ) -> list[FileInformation]:
        """Return the files of the content that have to be written."""
        if not contents:
            raise MarketplaceError(
                translation_domain=DOMAIN, translation_key="content_empty"
            )

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
                    translation_domain=DOMAIN,
                    translation_key="content_file_missing",
                    translation_placeholders={
                        "file": self.repository_manifest.filename
                    },
                )
            return wanted

        return contents

    async def download_repository_zip(self) -> None:
        """Download the zip archive of the repository."""
        ref = ref_version(self.ref)

        if not ref:
            raise MarketplaceError(
                translation_domain=DOMAIN, translation_key="version_unknown"
            )

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
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="archive_download_failed",
                translation_placeholders={"repository": self.data.full_name},
            )

        return await self.marketplace.hass.async_add_executor_job(
            RepositoryArchive, filecontent
        )

    async def _async_extract_archive(self, archive: RepositoryArchive) -> None:
        """Extract the remote directory of the content from the archive."""
        if (remote := self.content.path.remote) is None:
            raise MarketplaceError(
                translation_domain=DOMAIN, translation_key="content_location_unknown"
            )

        await self.marketplace.hass.async_add_executor_job(
            archive.extract_directory, remote, self.content.path.local
        )
        self.logger.info(
            "%s Content was extracted to %s", self.string, self.content.path.local
        )

    async def async_get_repository_manifest(self) -> dict[str, Any] | None:
        """Get the content of the hacs.json file."""
        try:
            response = await self.marketplace.async_github_api_method(
                method=self.marketplace.githubapi.repos.contents.get,
                raise_exception=False,
                repository=self.data.full_name,
                path=RepositoryFile.REPOSITORY_MANIFEST,
                params={"ref": self.version_to_install()},
            )
            if response:
                return json_loads_object(decode_content(response.data.content))
        except GitHubNotModifiedException, ValueError:
            pass
        return None

    async def async_get_readme_contents(self, *, version: str | None = None) -> str:
        """Get the content of the README, shown on the repository page."""
        # Without the tree, which only the GitHub API lists, the usual names are
        # tried. The files themselves are not counted against its rate limit.
        readme_files = (
            [filename for filename in README_FILENAMES if filename in self.treefiles]
            if self.treefiles
            else README_FILENAMES
        )

        for filename in readme_files:
            if content := await self.get_documentation(
                filename=filename, version=version
            ):
                return content
        return ""

    def remove(self) -> None:
        """Forget the repository, its files stay where they are."""
        if self.marketplace.repositories.is_registered(repository_id=self.data.id):
            self.logger.info("%s Starting removal", self.string)
            self.marketplace.repositories.unregister(self)

    @property
    def installing(self) -> bool:
        """Return True while the repository is being installed."""
        return self._install_lock.locked()

    async def uninstall(self) -> None:
        """Uninstall, not while an install of the repository is running."""
        if self.installing:
            raise RepositoryBusyError(self.data.full_name)

        async with self._install_lock:
            await self._async_uninstall()

    async def _async_uninstall(self) -> None:
        """Run uninstall tasks."""
        self.logger.info("%s Removing", self.string)
        if not await self.remove_local_directory():
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="uninstall_failed",
                translation_placeholders={"repository": self.data.full_name},
            )
        self.data.installed = False
        await self._async_post_uninstall()

        self.data.installed_version = None
        self.data.installed_commit = None
        self.async_dispatch_changed("uninstall")

        await self.async_remove_entity_device()
        ir.async_delete_issue(self.marketplace.hass, DOMAIN, f"removed_{self.data.id}")

    async def remove_local_directory(self) -> bool:
        """Remove the installed content, return if that worked."""

        local_path = self.content.path.local

        def _checked_path() -> str:
            """Return the path to remove, resolving it touches the disk."""
            checked = local_path
            if self.single_file:
                checked = str(entry_in_directory(checked, self.data.file_name))

            # The folder is named by remote input, removal stays inside its category
            if (directory := self._category_directory()) is not None:
                checked = str(entry_in_directory(directory, checked))
            return checked

        try:
            local_path = await self.marketplace.hass.async_add_executor_job(
                _checked_path
            )

            if await async_lexists(self.marketplace.hass, local_path):
                if not await self.marketplace.hass.async_add_executor_job(
                    is_safe, self.marketplace, local_path
                ):
                    self.logger.error(
                        "%s Path %s is blocked from removal", self.string, local_path
                    )
                    return False
                self.logger.debug("%s Removing %s", self.string, local_path)

                if self.single_file:
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
        return None

    async def async_pre_registration(self) -> None:
        """Run pre registration steps."""

    @concurrent(concurrenttasks=10)
    async def async_registration(self) -> None:
        """Run registration steps."""
        await self.async_pre_registration()

        if not await self.validate_repository():
            return

        await self.common_registration()
        self.content.path.local = self.localpath
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
            raise ReplacesBuiltInNotConfirmedError(
                self.data.full_name, str(self.data.domain)
            )
        await self.async_pre_install()
        self.logger.info("%s Pre installation steps completed", self.string)

    async def async_install(self, *, version: str | None = None) -> None:
        """Run install steps."""
        await self._async_run_install(
            partial(self._async_write_version, version=version)
        )

    async def _async_run_install(
        self, install_repository: Callable[[], Awaitable[None]]
    ) -> None:
        """Run the install steps around writing the content."""
        self._async_dispatch_install_progress(30)
        self.logger.info("%s Running installation steps", self.string)
        await install_repository()
        self._async_dispatch_install_progress(90)
        self.logger.info("%s Installation steps completed", self.string)
        await self._async_post_install()

    def _async_dispatch_install_progress(self, progress: int | Literal[False]) -> None:
        """Tell how far the install is, False once it is no longer running."""
        self.marketplace.async_dispatch(
            MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
            {"repository": self.data.full_name, "progress": progress},
        )

    def async_dispatch_changed(self, action: str) -> None:
        """Tell the panel the repository changed."""
        self.marketplace.async_dispatch(
            MarketplaceSignal.REPOSITORY,
            {
                "action": action,
                "repository": self.data.full_name,
                "repository_id": self.data.id,
            },
        )

    @contextmanager
    def _install_failure_names_the_version(self, version: str | None) -> Iterator[None]:
        """Name the repository and version in the error of a failed install."""
        try:
            yield
        except GitHubAnonymousRateLimitError, ReplacesBuiltInNotConfirmedError:
            raise
        except MarketplaceError as exception:
            # What the error tells is translated already, it keeps that
            if exception.translation_key:
                raise
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="install_version_failed",
                translation_placeholders={
                    "repository": self.data.full_name,
                    "version": str(version),
                    "error": str(exception),
                },
            ) from exception

    def _end_install(self) -> None:
        """Forget the version picked for the install and end its progress."""
        self.data.selected_tag = None
        self.force_branch = False
        self._async_dispatch_install_progress(False)

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
        try:
            await self.async_post_installation()
        except Exception as exception:
            # The files are in place, so is what the Marketplace knows of them
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="post_install_failed",
                translation_placeholders={"error": str(exception)},
            ) from exception
        finally:
            self.data.new = False
        self.logger.info("%s Post installation steps completed", self.string)

    async def _async_write_version(self, *, version: str | None = None) -> None:
        """Install a version through the GitHub API."""
        force_update = version is None or (
            self.data.last_version is not None and version != self.data.last_version
        )
        await self.update_repository(force=force_update)
        if self.content.path.local is None:
            raise MarketplaceError(
                translation_domain=DOMAIN, translation_key="content_location_unknown"
            )
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
        """Download a version, a ZIP release asset or its files."""
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
        self._async_dispatch_install_progress(40)

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

        self._async_dispatch_install_progress(50)

        try:
            await download()
            self._async_dispatch_install_progress(70)
            self._raise_for_install_errors()
            await self.async_check_written_content()

            # Into the new content, while the old one can still come back
            if persistent_directory is not None:
                await self.marketplace.hass.async_add_executor_job(
                    persistent_directory.restore
                )
        except (Exception, asyncio.CancelledError) as exception:
            # Whatever broke the install, the content that was there goes back,
            # also when it was cancelled
            await asyncio.shield(
                self.marketplace.hass.async_add_executor_job(_restore_backups)
            )
            if isinstance(exception, OSError):
                raise MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="content_write_failed",
                    translation_placeholders={"error": str(exception)},
                ) from exception
            raise

        self._async_dispatch_install_progress(80)

        try:
            if backup is not None:
                await self.marketplace.hass.async_add_executor_job(backup.cleanup)

            if persistent_directory is not None:
                await self.marketplace.hass.async_add_executor_job(
                    persistent_directory.cleanup
                )
        except OSError as exception:
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="backup_cleanup_failed",
                translation_placeholders={"error": str(exception)},
            ) from exception

    def _raise_for_install_errors(self) -> None:
        """Raise for the errors the install ran into, after logging them."""
        if not self.validate.errors:
            return

        for error in self.validate.errors:
            self.logger.error("%s %s", self.string, error)
        raise MarketplaceError(
            translation_domain=DOMAIN,
            translation_key="install_checks_failed",
            translation_placeholders={"repository": self.data.full_name},
        )

    async def _async_back_up_persistent_directory(self) -> Backup | None:
        """Move the directory hacs.json keeps across updates out of the way."""
        if not self.repository_manifest.persistent_directory:
            return None

        persistent_directory_name = self.repository_manifest.persistent_directory

        def _resolve() -> tuple[Path, Path]:
            """Return the content and the persistent directory in it, resolved."""
            local_path = Path(self.content.path.local).resolve()
            return local_path, resolve_in_directory(
                local_path, persistent_directory_name
            )

        (
            local_path,
            persistent_path,
        ) = await self.marketplace.hass.async_add_executor_job(_resolve)
        # Keeping all of the installed content would put the old version back over the new
        if persistent_path == local_path:
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="persistent_directory_invalid",
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
                raise GitHubAnonymousRateLimitError from exception
            raise MarketplaceError(
                translation_domain=DOMAIN, translation_key="rate_limited"
            ) from exception
        except GitHubAuthenticationException as exception:
            # Like every other GitHub call, a token that stopped working asks
            # the user to connect again
            if self.marketplace.github_connected:
                self.marketplace.disable(DisabledReason.INVALID_TOKEN)
            raise MarketplaceError(
                translation_domain=DOMAIN, translation_key="invalid_token"
            ) from exception
        except GitHubException as exception:
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="github_failed",
                translation_placeholders={"error": str(exception)},
            ) from exception

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
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="github_failed",
                translation_placeholders={"error": str(exception)},
            ) from exception
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
            if not is_valid_ref(release.tag_name):
                continue
            releases.append(release)
        return releases

    async def common_update_data(
        self, ignore_issues: bool = False, force: bool = False
    ) -> None:
        """Refresh the repository, its releases and the tree of the version to install."""
        if not await self._async_update_repository_object(
            ignore_issues=ignore_issues, force=force
        ):
            return

        if not ignore_issues:
            self._raise_when_unusable()

        await self._async_update_releases()
        if not self.force_branch:
            self.ref = self.version_to_install()
        self._update_download_count()

        await self._async_update_tree(ignore_issues=ignore_issues)

    async def _async_update_repository_object(
        self, *, ignore_issues: bool, force: bool
    ) -> bool:
        """Fetch the repository from GitHub, return False when it did not change."""
        try:
            repository_object, etag = await self.async_get_repository_object(
                etag=None
                if force or self.data.installed
                else self.data.etag_repository,
            )
        except NotModifiedError:
            self._reached()
            return False
        except GitHubAnonymousRateLimitError:
            raise
        except MarketplaceError as exception:
            self._not_reached(exception)
            if not ignore_issues:
                self.validate.errors.append(exception)
                raise
            return True

        self._reached()
        self.repository_object = repository_object
        if self.data.full_name.lower() != repository_object.full_name.lower():
            self.marketplace.common.renamed_repositories[self.data.full_name] = (
                repository_object.full_name
            )
            raise RepositoryExistsError

        self.data.update_data(repository_object.as_dict)
        self.data.etag_repository = etag
        return True

    def _not_reached(self, exception: MarketplaceError) -> None:
        """Mark the repository unreachable on GitHub, telling so once."""
        if self.unreachable:
            self.logger.debug("%s still can not be reached on GitHub", self.string)
            return

        self.logger.info("%s can not be reached on GitHub: %s", self.string, exception)
        self.unreachable = True

    def _reached(self) -> None:
        """Mark the repository reachable on GitHub, telling so when it was not."""
        if not self.unreachable:
            return

        self.logger.info("%s can be reached on GitHub again", self.string)
        self.unreachable = False

    def _raise_when_unusable(self) -> None:
        """Refuse a repository that is archived or asked to be removed."""
        if self.data.archived:
            archived = RepositoryArchivedError(
                translation_domain=DOMAIN,
                translation_key="repository_archived",
                translation_placeholders={"repository": self.data.full_name},
            )
            self.validate.errors.append(archived)
            self.marketplace.common.archived_repositories.add(self.data.full_name)
            raise archived

        if not self.marketplace.repositories.is_removed(self.data.full_name):
            return

        removed = self.marketplace.repositories.removed_repository(self.data.full_name)
        if removed.removal_type != "remove":
            removed_error = MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="repository_removed",
                translation_placeholders={"repository": self.data.full_name},
            )
            self.validate.errors.append(removed_error)
            raise removed_error

    async def _async_update_releases(self) -> None:
        """Take the newest version, pre-release and published versions from GitHub."""
        try:
            releases = await self.get_releases(prerelease=True, returnlimit=30)
        except GitHubAnonymousRateLimitError:
            raise
        except GitHubRateLimitError:
            # Running out of requests says nothing about the releases, the
            # anonymous limit runs out on browsing alone.
            self.logger.debug("%s Rate limited, keeping the releases", self.string)
            return
        except MarketplaceError:
            self.data.releases = False
            return

        if not releases:
            return

        # Newest first, a pre-release only counts when it is newer than the stable
        self.data.prerelease = None
        for release in releases:
            if not release.prerelease:
                self.data.last_version = release.tag_name
                break
            if self.data.prerelease is None:
                self.data.prerelease = release.tag_name

        self.data.releases = True
        self.releases.objects = [
            release
            for release in releases
            if self.data.show_beta or not release.prerelease
        ]
        self.data.published_tags = [
            release.tag_name for release in self.releases.objects
        ]

    def _update_download_count(self) -> None:
        """Take the download count from the asset of the release to install."""
        if not self.data.releases:
            return

        for release in self.releases.objects or []:
            if release.tag_name != self.ref:
                continue
            if target_asset := self._find_target_asset(release.assets):
                self.data.downloads = target_asset.download_count
            return

    async def _async_update_tree(self, *, ignore_issues: bool) -> None:
        """Fetch the tree of the version to install, the default one when it is gone."""
        try:
            try:
                await self._async_fetch_tree()
            except MarketplaceError as exception:
                if not isinstance(exception.__cause__, GitHubNotFoundException):
                    raise

                removed_ref = self.ref
                self.data.selected_tag = None
                self.ref = self.version_to_install()
                self.logger.warning(
                    "%s Version %s is no longer on GitHub, falling back to %s",
                    self.string,
                    removed_ref,
                    self.ref,
                )
                self._update_download_count()
                await self._async_fetch_tree()
        except GitHubAnonymousRateLimitError:
            raise
        except MarketplaceError as exception:
            if ignore_issues:
                return
            if not self.marketplace.status.startup:
                self.logger.error("%s %s", self.string, exception)
            raise

    async def _async_fetch_tree(self) -> None:
        """Fetch the tree of the version to install."""
        LOGGER.debug("%s Running checks against %s", self.string, ref_version(self.ref))
        if not (tree := await self.get_tree(self.ref)):
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="version_without_files",
                translation_placeholders={"version": str(ref_version(self.ref))},
            )

        self.tree = tree
        self.tree_ref = ref_version(self.ref)
        self.treefiles = [entry.path for entry in tree]

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

    def _tree_of_the_content(self) -> list[GitHubGitTreeEntryModel]:
        """Return the part of the tree the content is looked for in."""
        return self.tree

    def gather_tree_files_to_download(self) -> list[FileInformation]:
        """Return the files of the repository tree to be downloaded."""
        files: list[FileInformation] = []
        tree = self.tree

        if self.content.single:
            files.extend(
                self._tree_file_information(entry)
                for entry in tree
                if tree_entry_filename(entry) == self.data.file_name
            )
            return files

        for entry in self._tree_of_the_content():
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
                translation_domain=DOMAIN,
                translation_key="release_too_large",
                translation_placeholders={
                    "version": str(version),
                    "limit": str(MAX_DOWNLOAD_SIZE),
                },
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
    async def download_repository_file(self, content: FileInformation) -> None:
        """Download content."""
        self.logger.debug("%s Downloading %s", self.string, content.name)

        filecontent = await self.marketplace.async_download_file(content.download_url)

        if filecontent is None:
            self.validate.errors.append(
                MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="file_not_downloaded",
                    translation_placeholders={"file": content.name},
                )
            )
            return

        self._download_budget -= len(filecontent)
        if self._download_budget < 0:
            self.validate.errors.append(
                MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="content_over_limit",
                    translation_placeholders={
                        "file": content.name,
                        "limit": str(MAX_DOWNLOAD_SIZE),
                    },
                )
            )
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

            local_file_path = await self.marketplace.hass.async_add_executor_job(
                resolve_in_directory,
                self.content.path.local,
                f"{local_directory}/{content.name}",
            )

            result = await self.marketplace.async_save_file(
                str(local_file_path), filecontent
            )
            if result:
                self.logger.info(
                    "%s Download of %s completed", self.string, content.name
                )
                return
            self.validate.errors.append(
                MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="file_not_downloaded",
                    translation_placeholders={"file": content.name},
                )
            )

        except MarketplaceError as exception:
            self.validate.errors.append(exception)
        except OSError as exception:
            self.validate.errors.append(
                MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="download_incomplete",
                    translation_placeholders={"error": str(exception)},
                )
            )

    async def async_remove_entity_device(self) -> None:
        """Remove the entity device."""
        config_entry = self.marketplace.configuration.config_entry
        device_registry: dr.DeviceRegistry = dr.async_get(hass=self.marketplace.hass)
        identifier = (DOMAIN, self.data.id)

        # Looked up through our own config entry, since identifiers are only
        # guaranteed to be unique within a single config entry.
        for device in dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        ):
            if identifier in device.identifiers:
                device_registry.async_remove_device(device_id=device.id)
                return

    def version_to_install(self) -> str:
        """Return the version to install.

        Selecting the newest version forgets the selection, so the repository
        follows the versions that come after it.
        """
        if self.force_branch and self.ref is not None:
            return self.ref

        selected = self.data.selected_tag
        if self.data.last_version is not None:
            if selected is None or selected == self.data.last_version:
                self.data.selected_tag = None
                return self.data.last_version
            return selected

        if selected is not None and (
            selected == self.data.default_branch or selected in self.data.published_tags
        ):
            return selected

        return self.data.default_branch or "main"

    async def get_documentation(
        self,
        *,
        filename: str | None = None,
        version: str | None = None,
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
        self, *, version: str | None
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

        if asset_names := self._release_asset_names():
            for asset in assets:
                if asset.name in asset_names:
                    return asset

        if target_filename := self.repository_manifest.filename:
            for asset in assets:
                if asset.name == target_filename:
                    return asset

        return assets[0] if assets else None

    def _release_asset_names(self) -> tuple[str, ...]:
        """Return the names the release asset with the content can have."""
        return ()

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

    async def _ensure_install_capabilities(self, ref: str | None) -> None:
        """Ensure that the install can be handled."""
        target_manifest: RepositoryManifest | None = None
        if ref is None:
            if not self.can_install:
                raise MarketplaceError(
                    translation_domain=DOMAIN,
                    translation_key="not_installable",
                    translation_placeholders={"repository": self.data.full_name},
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
                translation_domain=DOMAIN,
                translation_key="version_without_repository_manifest",
                translation_placeholders={
                    "repository": self.data.full_name,
                    "version": ref,
                },
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
                translation_domain=DOMAIN,
                translation_key="requires_newer_home_assistant",
                translation_placeholders={"version": str(manifest.homeassistant)},
            )

    async def async_install_repository(
        self,
        *,
        ref: str | None = None,
        confirm_replace_built_in: bool = False,
    ) -> None:
        """Install a repository."""
        if self.installing:
            raise RepositoryBusyError(self.data.full_name)

        async with self._install_lock:
            self._replace_built_in_confirmed = confirm_replace_built_in
            try:
                await self._async_install_repository(ref)
            finally:
                self._replace_built_in_confirmed = False
                # Installs also come from update entities and automations, the
                # state is stored once for all of them, also when a step failed
                await self.marketplace.data.async_write()

    async def async_wait_for_install(self) -> None:
        """Wait for an install of this repository that is running to finish."""
        if not self.installing:
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
        try:
            if self.display_version_or_commit == "version":
                self._async_dispatch_install_progress(10)
                if not ref:
                    await self.update_repository(force=True)
                else:
                    self.ref = ref
                self.data.selected_tag = ref
                self.force_branch = ref is not None
                self._async_dispatch_install_progress(20)

            with self._install_failure_names_the_version(
                ref or self.data.last_version or self.data.last_commit
            ):
                await self.async_install(version=ref)
        finally:
            self._end_install()

    def _catalog_version(self, ref: str | None) -> str | None:
        """Return the catalog version to install without the GitHub API.

        Anonymous access to the API runs out after a handful of installs. The
        catalog already names the version, and the files come from hosts
        without that limit. A version the user picked keeps using the API.
        """
        if not self.marketplace.repositories.is_default(self.data.id):
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
                translation_domain=DOMAIN,
                translation_key="not_installable",
                translation_placeholders={"repository": self.data.full_name},
            )

        # Without releases the catalog names the last commit instead
        commit = self.data.last_version is None
        self.logger.info("Starting install, %s", version)
        self._async_dispatch_install_progress(10)

        try:
            download = await self._async_prepare_catalog_install(version, commit=commit)
            self._async_dispatch_install_progress(20)

            with self._install_failure_names_the_version(version):
                await self._async_run_install(
                    partial(
                        self._async_write_catalog_version,
                        version,
                        download,
                        commit=commit,
                    )
                )
        finally:
            self._end_install()

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
        # A tag ends up in the URLs the version is installed by
        releases: list[GitHubReleaseModel] = [
            release for release in response.data if is_valid_ref(release.tag_name)
        ]
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
