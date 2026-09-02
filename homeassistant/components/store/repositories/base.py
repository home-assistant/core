"""Repository."""

from __future__ import annotations

from asyncio import sleep
from datetime import UTC, datetime
import os
import pathlib
import shutil
import tempfile
from typing import TYPE_CHECKING, Any
import zipfile

from aiogithubapi import (
    AIOGitHubAPIException,
    AIOGitHubAPINotModifiedException,
    GitHubException,
)
import attr
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from ..const import DOMAIN
from ..enums import HacsDispatchEvent, RepositoryFile
from ..exceptions import (
    HacsException,
    HacsNotModifiedException,
    HacsRepositoryArchivedException,
    HacsRepositoryExistException,
)
from ..types import DownloadableContent
from ..utils.backup import Backup
from ..utils.decode import decode_content
from ..utils.decorator import concurrent, return_none_on_exception
from ..utils.file_system import async_exists, async_remove, async_remove_directory
from ..utils.filters import filter_content_return_one_of_type
from ..utils.json import json_loads
from ..utils.logger import LOGGER
from ..utils.path import is_safe
from ..utils.queue_manager import QueueManager
from ..utils.store import async_remove_store
from ..utils.url import github_archive, github_release_asset
from ..utils.validate import Validate
from ..utils.version import (
    version_left_higher_or_equal_then_right,
    version_left_higher_then_right,
)
from ..utils.workarounds import DOMAIN_OVERRIDES, LegacyTreeFile

if TYPE_CHECKING:
    from aiogithubapi.models.git_tree import GitHubGitTreeEntryModel
    from aiogithubapi.models.release import GitHubReleaseAssetModel, GitHubReleaseModel
    from aiogithubapi.objects.repository import AIOGitHubAPIRepository

    from ..base import HacsBase


TOPIC_FILTER = (
    "add-on",
    "addon",
    "app",
    "appdaemon-apps",
    "appdaemon",
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


REPOSITORY_KEYS_TO_EXPORT = (
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

HACS_MANIFEST_KEYS_TO_EXPORT = (
    # Keys can not be removed from this list until v3
    # If keys are added, the action need to be re-run with force
    ("country", []),
    ("name", None),
)


class FileInformation:
    """FileInformation."""

    def __init__(self, url, path, name):
        self.download_url = url
        self.path = path
        self.name = name


@attr.s(auto_attribs=True)
class RepositoryData:
    """RepositoryData class."""

    archived: bool = False
    authors: list[str] = []
    category: str = ""
    config_flow: bool = False
    default_branch: str = None
    description: str = ""
    domain: str = None
    downloads: int = 0
    etag_repository: str = None
    etag_releases: str = None
    file_name: str = ""
    first_install: bool = False
    full_name: str = ""
    hide: bool = False
    has_issues: bool = True
    id: int = 0
    installed_commit: str = None
    installed_version: str = None
    installed: bool = False
    last_commit: str = None
    last_fetched: datetime = None
    last_updated: str = 0
    last_version: str = None
    manifest_name: str = None
    new: bool = True
    open_issues: int = 0
    prerelease: str = None
    published_tags: list[str] = []
    releases: bool = False
    selected_tag: str = None
    show_beta: bool = False
    stargazers_count: int = 0
    topics: list[str] = []

    @property
    def name(self):
        """Return the name."""
        if self.category == "integration":
            return self.domain
        return self.full_name.split("/")[-1]

    def to_json(self):
        """Export to json."""
        return attr.asdict(self, filter=lambda attr, value: attr.name != "last_fetched")

    @staticmethod
    def create_from_dict(source: dict, action: bool = False) -> RepositoryData:
        """Set attributes from dicts."""
        data = RepositoryData()
        data.update_data(source, action)
        return data

    def update_data(self, data: dict, action: bool = False) -> None:
        """Update data of the repository."""
        for key, value in data.items():
            if key not in self.__dict__:
                continue

            if key == "last_fetched" and isinstance(value, float):
                setattr(self, key, datetime.fromtimestamp(value, UTC))
            elif key == "id":
                setattr(self, key, str(value))
            elif key == "topics" and not action:
                setattr(self, key, [topic for topic in value if topic not in TOPIC_FILTER])

            else:
                setattr(self, key, value)


@attr.s(auto_attribs=True)
class HacsManifest:
    """HacsManifest class."""

    content_in_root: bool = False
    country: list[str] = []
    filename: str = None
    hacs: str = None  # Minimum HACS version
    hide_default_branch: bool = False
    homeassistant: str = None  # Minimum Home Assistant version
    manifest: dict = {}
    name: str = None
    persistent_directory: str = None
    render_readme: bool = False
    zip_release: bool = False

    def to_dict(self):
        """Export to json."""
        return attr.asdict(self)

    @staticmethod
    def from_dict(manifest: dict):
        """Set attributes from dicts."""
        if manifest is None:
            raise HacsException("Missing manifest data")

        manifest_data = HacsManifest()
        manifest_data.manifest = {
            k: v
            for k, v in manifest.items()
            if k in manifest_data.__dict__ and v != manifest_data.__getattribute__(k)
        }

        for key, value in manifest_data.manifest.items():
            if key == "country" and isinstance(value, str):
                setattr(manifest_data, key, [value])
            elif key in manifest_data.__dict__:
                setattr(manifest_data, key, value)
        return manifest_data

    def update_data(self, data: dict) -> None:
        """Update the manifest data."""
        for key, value in data.items():
            if key not in self.__dict__:
                continue

            if key == "country":
                if isinstance(value, str):
                    setattr(self, key, [value])
                else:
                    setattr(self, key, value)
            else:
                setattr(self, key, value)


class RepositoryReleases:
    """RepositoyReleases."""

    last_release = None
    last_release_object = None
    published_tags = []
    objects: list[GitHubReleaseModel] = []
    releases = False
    downloads = None


class RepositoryPath:
    """RepositoryPath."""

    local: str | None = None
    remote: str | None = None


class RepositoryContent:
    """RepositoryContent."""

    path: RepositoryPath | None = None
    files = []
    objects = []
    single = False


class HacsRepository:
    """HacsRepository."""

    def __init__(self, hacs: HacsBase) -> None:
        """Set up HacsRepository."""
        self.hacs = hacs
        self.additional_info = ""
        self.data = RepositoryData()
        self.content = RepositoryContent()
        self.content.path = RepositoryPath()
        self.repository_object: AIOGitHubAPIRepository | None = None
        self.updated_info = False
        self.state = None
        self.force_branch = False
        self.integration_manifest = {}
        self.repository_manifest = HacsManifest.from_dict({})
        self.validate = Validate()
        self.releases = RepositoryReleases()
        self.pending_restart = False
        self.tree = []
        self.treefiles = []
        self.ref = None
        self.logger = LOGGER

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
                return self.integration_manifest["name"]

        return self.data.full_name.split("/")[-1].replace("-", " ").replace("_", " ").title()

    @property
    def ignored_by_country_configuration(self) -> bool:
        """Return True if hidden by country."""
        if self.data.installed:
            return False
        configuration = self.hacs.configuration.country.lower()
        if configuration == "all":
            return False

        manifest = [entry.lower() for entry in self.repository_manifest.country or []]
        if not manifest:
            return False
        return configuration not in manifest

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
        """Return display_authors"""
        if self.data.installed_version is not None:
            installed = self.data.installed_version
        else:
            if self.data.installed_commit is not None:
                installed = self.data.installed_commit
            else:
                installed = ""
        return str(installed)

    @property
    def display_available_version(self) -> str:
        """Return display_authors"""
        if self.data.show_beta and self.data.prerelease is not None:
            available = self.data.prerelease
        elif self.data.last_version is not None:
            available = self.data.last_version
        else:
            if self.data.last_commit is not None:
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
            if self.display_version_or_commit == "version":
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
    def can_download(self) -> bool:
        """Return True if we can download."""
        if self.repository_manifest.homeassistant is not None:
            if self.data.releases:
                if not version_left_higher_or_equal_then_right(
                    self.hacs.core.ha_version.string,
                    self.repository_manifest.homeassistant,
                ):
                    return False
        return True

    @property
    def localpath(self) -> str | None:
        """Return localpath."""
        return None

    @property
    def should_try_releases(self) -> bool:
        """Return a boolean indicating whether to download releases or not."""
        if self.repository_manifest.zip_release:
            if self.repository_manifest.filename.endswith(".zip"):
                if self.ref != self.data.default_branch:
                    return True
        if self.ref == self.data.default_branch:
            return False
        if self.data.category not in ["plugin", "theme"]:
            return False
        if not self.data.releases:
            return False
        return True

    async def validate_repository(self) -> None:
        """Validate."""

    @concurrent(concurrenttasks=10, backoff_time=5)
    async def update_repository(self, ignore_issues=False, force=False) -> None:
        """Update the repository"""

    async def common_validate(self, ignore_issues: bool = False) -> None:
        """Common validation steps of the repository."""
        self.validate.errors.clear()

        # Make sure the repository exist.
        self.logger.debug("%s Checking repository.", self.string)
        await self.common_update_data(ignore_issues=ignore_issues)

        # Get the content of hacs.json
        if RepositoryFile.HACS_JSON in [x.filename for x in self.tree]:
            if manifest := await self.async_get_hacs_json():
                self.repository_manifest = HacsManifest.from_dict(manifest)
                self.data.update_data(
                    self.repository_manifest.to_dict(),
                    action=self.hacs.system.action,
                )

    async def common_registration(self) -> None:
        """Common registration steps of the repository."""
        # Attach repository
        if self.repository_object is None:
            try:
                self.repository_object, etag = await self.async_get_legacy_repository_object(
                    etag=None if self.data.installed else self.data.etag_repository,
                )
                self.data.update_data(
                    self.repository_object.attributes,
                    action=self.hacs.system.action,
                )
                self.data.etag_repository = etag
            except HacsNotModifiedException:
                self.logger.debug("%s Did not update, content was not modified", self.string)
                return

        if self.repository_object:
            self.data.last_updated = self.repository_object.attributes.get("pushed_at", 0)
            self.data.last_fetched = datetime.now(UTC)

    @concurrent(concurrenttasks=10, backoff_time=5)
    async def common_update(self, ignore_issues=False, force=False, skip_releases=False) -> bool:
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
        except HacsRepositoryExistException:
            self.data.full_name = self.hacs.common.renamed_repositories[self.data.full_name]
            await self.common_update_data(ignore_issues=ignore_issues, force=force)

        except HacsException:
            if not ignore_issues and not force:
                return False

        if not self.data.installed and (current_etag == self.data.etag_repository) and not force:
            self.logger.debug("%s Did not update, content was not modified", self.string)
            return False

        # Update last updated
        if self.repository_object:
            self.data.last_updated = self.repository_object.attributes.get("pushed_at", 0)

            # Update last available commit
            await self.async_set_last_commits()

        # Get the content of hacs.json
        if RepositoryFile.HACS_JSON in [x.filename for x in self.tree]:
            if manifest := await self.async_get_hacs_json():
                self.repository_manifest = HacsManifest.from_dict(manifest)
                self.data.update_data(
                    self.repository_manifest.to_dict(),
                    action=self.hacs.system.action,
                )

        # Update "info.md"
        self.additional_info = await self.async_get_info_file_contents()

        # Set last fetch attribute
        self.data.last_fetched = datetime.now(UTC)

        return True

    async def download_zip_files(self, validate: Validate) -> None:
        """Download ZIP archive from repository release."""

        try:
            await self.async_download_zip_file(
                DownloadableContent(
                    name=self.repository_manifest.filename,
                    url=github_release_asset(
                        repository=self.data.full_name,
                        version=self.ref,
                        filename=self.repository_manifest.filename,
                    ),
                ),
                validate,
            )
        # lgtm [py/catch-base-exception] pylint: disable=broad-except
        except BaseException:
            validate.errors.append(
                f"Download of {self.repository_manifest.filename} was not completed"
            )

    async def async_download_zip_file(
        self,
        content: DownloadableContent,
        validate: Validate,
    ) -> None:
        """Download ZIP archive from repository release."""
        try:
            filecontent = await self.hacs.async_download_file(content["url"])

            if filecontent is None:
                validate.errors.append(f"Failed to download {content['url']}")
                return

            temp_dir = await self.hacs.hass.async_add_executor_job(tempfile.mkdtemp)
            temp_file = f"{temp_dir}/{self.repository_manifest.filename}"

            result = await self.hacs.async_save_file(temp_file, filecontent)

            def _extract_zip_file():
                with zipfile.ZipFile(temp_file, "r") as zip_file:
                    zip_file.extractall(self.content.path.local)

            await self.hacs.hass.async_add_executor_job(_extract_zip_file)

            def cleanup_temp_dir():
                """Cleanup temp_dir."""
                if os.path.exists(temp_dir):
                    self.logger.debug("%s Cleaning up %s", self.string, temp_dir)
                    shutil.rmtree(temp_dir)

            if result:
                self.logger.info("%s Download of %s completed", self.string, content["name"])
                await self.hacs.hass.async_add_executor_job(cleanup_temp_dir)
                return

            validate.errors.append(f"[{content['name']}] was not downloaded")
        # lgtm [py/catch-base-exception] pylint: disable=broad-except
        except BaseException:
            validate.errors.append("Download was not completed")

    async def download_content(self, version: string | None = None) -> None:
        """Download the content of a directory."""
        contents: list[FileInformation] | None = None
        if (
            not self.repository_manifest.zip_release
            and not self.data.file_name
            and self.content.path.remote is not None
        ):
            self.logger.info("%s Downloading repository archive", self.string)
            try:
                await self.download_repository_zip()
                return
            except HacsException as exception:
                self.logger.exception(exception)

        if self.repository_manifest.filename:
            self.logger.debug("%s %s", self.string, self.repository_manifest.filename)

        if self.content.path.remote == "release" and version is not None:
            contents = await self.release_contents(version)

        if not contents:
            contents = self.gather_files_to_download()

        if not contents:
            raise HacsException("No content to download")

        download_queue = QueueManager(hass=self.hacs.hass)

        for content in contents:
            if self.repository_manifest.content_in_root and self.repository_manifest.filename:
                if content.name != self.repository_manifest.filename:
                    continue
            download_queue.add(self.dowload_repository_content(content))

        await download_queue.execute()

    async def download_repository_zip(self):
        """Download the zip archive of the repository."""
        ref = f"{self.ref}".replace("tags/", "")

        if not ref:
            raise HacsException("Missing required elements.")

        filecontent = await self.hacs.async_download_file(
            github_archive(repository=self.data.full_name, version=ref, variant="tags"),
            keep_url=True,
            nolog=True,
        )

        if filecontent is None:
            filecontent = await self.hacs.async_download_file(
                github_archive(repository=self.data.full_name, version=ref, variant="heads"),
                keep_url=True,
            )
        if filecontent is None:
            raise HacsException(f"[{self}] Failed to download zipball")

        temp_dir = await self.hacs.hass.async_add_executor_job(tempfile.mkdtemp)
        temp_file = f"{temp_dir}/{self.repository_manifest.filename}"
        result = await self.hacs.async_save_file(temp_file, filecontent)
        if not result:
            raise HacsException("Could not save ZIP file")

        def _extract_zip_file():
            with zipfile.ZipFile(temp_file, "r") as zip_file:
                extractable = []
                for path in zip_file.filelist:
                    filename = "/".join(path.filename.split("/")[1:])
                    if (
                        filename.startswith(self.content.path.remote)
                        and filename != self.content.path.remote
                    ):
                        path.filename = filename.replace(self.content.path.remote, "")
                        if path.filename == "/":
                            # Blank files is not valid, and will start to throw in Python 3.12
                            continue
                        extractable.append(path)

                if len(extractable) == 0:
                    raise HacsException("No content to extract")
                zip_file.extractall(self.content.path.local, extractable)

        await self.hacs.hass.async_add_executor_job(_extract_zip_file)

        def cleanup_temp_dir():
            """Cleanup temp_dir."""
            if os.path.exists(temp_dir):
                self.logger.debug("%s Cleaning up %s", self.string, temp_dir)
                shutil.rmtree(temp_dir)

        await self.hacs.hass.async_add_executor_job(cleanup_temp_dir)
        self.logger.info("%s Content was extracted to %s", self.string, self.content.path.local)

    async def async_get_hacs_json(self, ref: str = None) -> dict[str, Any] | None:
        """Get the content of the hacs.json file."""
        try:
            response = await self.hacs.async_github_api_method(
                method=self.hacs.githubapi.repos.contents.get,
                raise_exception=False,
                repository=self.data.full_name,
                path=RepositoryFile.HACS_JSON,
                **{"params": {"ref": ref or self.version_to_download()}},
            )
            if response:
                return json_loads(decode_content(response.data.content))
        # lgtm [py/catch-base-exception] pylint: disable=broad-except
        except BaseException:
            pass

    async def async_get_info_file_contents(self, *, version: str | None = None, **kwargs) -> str:
        """Get the content of the info.md file."""

        def _info_file_variants() -> tuple[str, ...]:
            name: str = "readme"
            return (
                f"{name.upper()}.md",
                f"{name}.md",
                f"{name}.MD",
                f"{name.upper()}.MD",
                name.upper(),
                name,
            )

        info_files = [filename for filename in _info_file_variants() if filename in self.treefiles]

        if not info_files:
            return ""

        return await self.get_documentation(filename=info_files[0], version=version) or ""

    def remove(self) -> None:
        """Run remove tasks."""
        if self.hacs.repositories.is_registered(repository_id=str(self.data.id)):
            self.logger.info("%s Starting removal", self.string)
            self.hacs.repositories.unregister(self)

    async def uninstall(self) -> None:
        """Run uninstall tasks."""
        self.logger.info("%s Removing", self.string)
        if not await self.remove_local_directory():
            raise HacsException("Could not uninstall")
        self.data.installed = False
        await self._async_post_uninstall()
        await async_remove_store(self.hacs.hass, f"hacs/{self.data.id}.hacs")

        self.data.installed_version = None
        self.data.installed_commit = None
        self.hacs.async_dispatch(
            HacsDispatchEvent.REPOSITORY,
            {
                "id": 1337,
                "action": "uninstall",
                "repository": self.data.full_name,
                "repository_id": self.data.id,
            },
        )

        await self.async_remove_entity_device()
        ir.async_delete_issue(self.hacs.hass, DOMAIN, f"removed_{self.data.id}")

    async def remove_local_directory(self) -> None:
        """Check the local directory."""

        try:
            if self.data.category == "python_script":
                local_path = f"{self.content.path.local}/{self.data.file_name}"
            elif self.data.category == "template":
                local_path = f"{self.content.path.local}/{self.data.file_name}"
            elif self.data.category == "theme":
                path = (
                    f"{self.hacs.core.config_path}/"
                    f"{self.hacs.configuration.theme_path}/"
                    f"{self.data.name}.yaml"
                )
                await async_remove(self.hacs.hass, path, missing_ok=True)
                local_path = self.content.path.local
            elif self.data.category == "integration":
                if not self.data.domain:
                    if domain := DOMAIN_OVERRIDES.get(self.data.full_name):
                        self.data.domain = domain
                        self.content.path.local = self.localpath
                    else:
                        self.logger.error("%s Missing domain", self.string)
                        return False
                local_path = self.content.path.local
            else:
                local_path = self.content.path.local

            if await async_exists(self.hacs.hass, local_path):
                if not is_safe(self.hacs, local_path):
                    self.logger.error("%s Path %s is blocked from removal", self.string, local_path)
                    return False
                self.logger.debug("%s Removing %s", self.string, local_path)

                if self.data.category in ["python_script", "template"]:
                    await async_remove(self.hacs.hass, local_path)
                else:
                    await async_remove_directory(self.hacs.hass, local_path)

                while await async_exists(self.hacs.hass, local_path):
                    await sleep(1)
            else:
                self.logger.debug(
                    "%s Presumed local content path %s does not exist", self.string, local_path
                )

        except (
            # lgtm [py/catch-base-exception] pylint: disable=broad-except
            BaseException
        ) as exception:
            self.logger.debug("%s Removing %s failed with %s", self.string, local_path, exception)
            return False
        return True

    async def async_pre_registration(self) -> None:
        """Run pre registration steps."""

    @concurrent(concurrenttasks=10)
    async def async_registration(self, ref=None) -> None:
        """Run registration steps."""
        await self.async_pre_registration()

        if ref is not None:
            self.data.selected_tag = ref
            self.ref = ref
            self.force_branch = True

        if not await self.validate_repository():
            return False

        # Run common registration steps.
        await self.common_registration()

        # Set correct local path
        self.content.path.local = self.localpath

        # Run local post registration steps.
        await self.async_post_registration()

    async def async_post_registration(self) -> None:
        """Run post registration steps."""
        if not self.hacs.system.action:
            return
        await self.hacs.validation.async_run_repository_checks(self)

    async def async_pre_install(self) -> None:
        """Run pre install steps."""

    async def _async_pre_install(self) -> None:
        """Run pre install steps."""
        self.logger.info("%s Running pre installation steps", self.string)
        await self.async_pre_install()
        self.logger.info("%s Pre installation steps completed", self.string)

    async def async_install(self, *, version: str | None = None, **_) -> None:
        """Run install steps."""
        await self._async_pre_install()
        self.hacs.async_dispatch(
            HacsDispatchEvent.REPOSITORY_DOWNLOAD_PROGRESS,
            {"repository": self.data.full_name, "progress": 30},
        )
        self.logger.info("%s Running installation steps", self.string)
        await self.async_install_repository(version=version)
        self.hacs.async_dispatch(
            HacsDispatchEvent.REPOSITORY_DOWNLOAD_PROGRESS,
            {"repository": self.data.full_name, "progress": 90},
        )
        self.logger.info("%s Installation steps completed", self.string)
        await self._async_post_install()
        self.hacs.async_dispatch(
            HacsDispatchEvent.REPOSITORY_DOWNLOAD_PROGRESS,
            {"repository": self.data.full_name, "progress": False},
        )

    async def async_post_installation(self) -> None:
        """Run post install steps."""

    async def async_post_uninstall(self):
        """Run post uninstall steps."""

    async def _async_post_uninstall(self):
        """Run post uninstall steps."""
        await self.async_post_uninstall()

    async def _async_post_install(self) -> None:
        """Run post install steps."""
        self.logger.info("%s Running post installation steps", self.string)
        await self.async_post_installation()
        self.data.new = False
        self.hacs.async_dispatch(
            HacsDispatchEvent.REPOSITORY,
            {
                "id": 1337,
                "action": "install",
                "repository": self.data.full_name,
                "repository_id": self.data.id,
            },
        )
        self.logger.info("%s Post installation steps completed", self.string)

    async def async_install_repository(self, *, version: str | None = None, **_) -> None:
        """Common installation steps of the repository."""
        persistent_directory = None
        force_update = version is None or (
            self.data.last_version is not None and version != self.data.last_version
        )
        await self.update_repository(force=force_update)
        if self.content.path.local is None:
            raise HacsException("repository.content.path.local is None")
        self.validate.errors.clear()

        version_to_install = version or self.version_to_download()
        if version_to_install == self.data.default_branch:
            self.ref = version_to_install
        else:
            self.ref = f"tags/{version_to_install}"

        self.hacs.async_dispatch(
            HacsDispatchEvent.REPOSITORY_DOWNLOAD_PROGRESS,
            {"repository": self.data.full_name, "progress": 40},
        )

        if self.repository_manifest.persistent_directory:
            if await async_exists(
                self.hacs.hass,
                f"{self.content.path.local}/{self.repository_manifest.persistent_directory}",
            ):
                persistent_directory = Backup(
                    hacs=self.hacs,
                    local_path=f"{self.content.path.local}/{self.repository_manifest.persistent_directory}",
                    backup_path=tempfile.gettempdir() + "/hacs_persistent_directory/",
                )
                await self.hacs.hass.async_add_executor_job(persistent_directory.create)

        if self.data.installed and not self.content.single:
            backup = Backup(hacs=self.hacs, local_path=self.content.path.local)
            await self.hacs.hass.async_add_executor_job(backup.create)

        self.hacs.log.debug("%s Local path is set to %s", self.string, self.content.path.local)
        self.hacs.log.debug("%s Remote path is set to %s", self.string, self.content.path.remote)
        self.hacs.log.debug("%s Version to install: %s", self.string, version_to_install)

        self.hacs.async_dispatch(
            HacsDispatchEvent.REPOSITORY_DOWNLOAD_PROGRESS,
            {"repository": self.data.full_name, "progress": 50},
        )

        if self.repository_manifest.zip_release and self.repository_manifest.filename:
            await self.download_zip_files(self.validate)
        else:
            await self.download_content(version_to_install)

        self.hacs.async_dispatch(
            HacsDispatchEvent.REPOSITORY_DOWNLOAD_PROGRESS,
            {"repository": self.data.full_name, "progress": 70},
        )

        if self.validate.errors:
            for error in self.validate.errors:
                self.logger.error("%s %s", self.string, error)
            if self.data.installed and not self.content.single:
                await self.hacs.hass.async_add_executor_job(backup.restore)
                await self.hacs.hass.async_add_executor_job(backup.cleanup)
            raise HacsException("Could not download, see log for details")

        self.hacs.async_dispatch(
            HacsDispatchEvent.REPOSITORY_DOWNLOAD_PROGRESS,
            {"repository": self.data.full_name, "progress": 80},
        )

        if self.data.installed and not self.content.single:
            await self.hacs.hass.async_add_executor_job(backup.cleanup)

        if persistent_directory is not None:
            await self.hacs.hass.async_add_executor_job(persistent_directory.restore)
            await self.hacs.hass.async_add_executor_job(persistent_directory.cleanup)

        if self.validate.success:
            self.data.installed = True
            self.data.installed_commit = self.data.last_commit

            if version_to_install == self.data.default_branch:
                self.data.installed_version = None
            else:
                self.data.installed_version = version_to_install

    async def async_get_legacy_repository_object(
        self,
        etag: str | None = None,
    ) -> tuple[AIOGitHubAPIRepository, Any | None]:
        """Return a repository object."""
        try:
            repository = await self.hacs.github.get_repo(self.data.full_name, etag)
            return repository, self.hacs.github.client.last_response.etag
        except AIOGitHubAPINotModifiedException as exception:
            raise HacsNotModifiedException(exception) from exception
        except (ValueError, AIOGitHubAPIException, Exception) as exception:
            raise HacsException(exception) from exception

    def update_filenames(self) -> None:
        """Get the filename to target."""

    async def get_tree(self, ref: str) -> list[GitHubGitTreeEntryModel] | None:
        """Return the repository tree."""
        try:
            response = await self.hacs.async_github_api_method(
                method=self.hacs.githubapi.repos.git.get_tree,
                repository=self.data.full_name,
                tree_sha=ref,
                params={"recursive": "true"},
            )
            return response.data.tree
        except GitHubException as exception:
            raise HacsException(exception) from exception

    async def get_releases(self, prerelease=False, returnlimit=5) -> list[GitHubReleaseModel]:
        """Return the repository releases."""
        response = await self.hacs.async_github_api_method(
            method=self.hacs.githubapi.repos.releases.list,
            repository=self.data.full_name,
        )
        releases = []
        for release in response.data or []:
            if len(releases) == returnlimit:
                break
            if release.draft or (release.prerelease and not prerelease):
                continue
            releases.append(release)
        return releases

    async def common_update_data(
        self,
        ignore_issues: bool = False,
        force: bool = False,
        retry=False,
        skip_releases=False,
    ) -> None:
        """Common update data."""
        releases = []
        try:
            repository_object, etag = await self.async_get_legacy_repository_object(
                etag=None if force or self.data.installed else self.data.etag_repository,
            )
            self.repository_object = repository_object
            if self.data.full_name.lower() != repository_object.full_name.lower():
                self.hacs.common.renamed_repositories[self.data.full_name] = (
                    repository_object.full_name
                )
                if not self.hacs.system.generator:
                    raise HacsRepositoryExistException
                self.logger.error(
                    "%s Repository has been renamed - %s", self.string, repository_object.full_name
                )
            self.data.update_data(
                repository_object.attributes,
                action=self.hacs.system.action,
            )
            self.data.etag_repository = etag
        except HacsNotModifiedException:
            return
        except HacsRepositoryExistException:
            raise HacsRepositoryExistException from None
        except (AIOGitHubAPIException, HacsException) as exception:
            if not self.hacs.status.startup or self.hacs.system.generator:
                self.logger.error("%s %s", self.string, exception)
            if not ignore_issues:
                self.validate.errors.append("Repository does not exist.")
                raise HacsException(exception) from exception

        # Make sure the repository is not archived.
        if self.data.archived and not ignore_issues:
            self.validate.errors.append("Repository is archived.")
            if self.data.full_name not in self.hacs.common.archived_repositories:
                self.hacs.common.archived_repositories.add(self.data.full_name)
            raise HacsRepositoryArchivedException(f"{self} Repository is archived.")

        # Make sure the repository is not in the blacklist.
        if self.hacs.repositories.is_removed(self.data.full_name):
            removed = self.hacs.repositories.removed_repository(self.data.full_name)
            if removed.removal_type != "remove" and not ignore_issues:
                self.validate.errors.append("Repository has been requested to be removed.")
                raise HacsException(f"{self} Repository has been requested to be removed.")

        # Get releases.
        if not skip_releases:
            try:
                releases = await self.get_releases(prerelease=True, returnlimit=30)
                if releases:
                    self.data.prerelease = None
                    for release in releases:
                        if release.draft:
                            continue
                        elif release.prerelease:
                            if self.data.prerelease is None:
                                self.data.prerelease = release.tag_name
                        else:
                            self.data.last_version = release.tag_name
                            break

                    self.data.releases = True

                    filtered_releases = [
                        release
                        for release in releases
                        if not release.draft and (self.data.show_beta or not release.prerelease)
                    ]
                    self.releases.objects = filtered_releases
                    self.data.published_tags = [x.tag_name for x in filtered_releases]

            except HacsException:
                self.data.releases = False

        if not self.force_branch:
            self.ref = self.version_to_download()
        if self.data.releases:
            for release in self.releases.objects or []:
                if release.tag_name == self.ref:
                    if assets := release.assets:
                        if target_asset := self._find_target_asset(assets):
                            self.data.downloads = target_asset.download_count
        elif self.hacs.system.generator and self.repository_object:
            await self.async_set_last_commits()

        self.hacs.log.debug(
            "%s Running checks against %s", self.string, self.ref.replace("tags/", "")
        )

        try:
            tree = await self.get_tree(self.ref)
            if not tree:
                raise HacsException("No files in tree")
            self.tree = [
                LegacyTreeFile(entry, repository=self.data.full_name, ref=self.ref)
                for entry in tree
            ]

            self.treefiles = []
            for treefile in self.tree:
                self.treefiles.append(treefile.full_path)
        except HacsException as exception:
            if (
                not retry
                and self.ref is not None
                and str(exception).startswith("GitHub returned 404")
            ):
                # Handle tags/branches being deleted.
                self.data.selected_tag = None
                self.ref = self.version_to_download()
                self.logger.warning(
                    "%s Selected version/branch %s has been removed, falling back to default",
                    self.string,
                    self.ref,
                )
                return await self.common_update_data(ignore_issues, force, True)
            if not self.hacs.status.startup and not ignore_issues:
                self.logger.error("%s %s", self.string, exception)
            if not ignore_issues:
                raise HacsException(exception) from None

    def gather_files_to_download(self) -> list[FileInformation]:
        """Return a list of file objects to be downloaded."""
        files = []
        tree = self.tree
        ref = f"{self.ref}".replace("tags/", "")
        releaseobjects = self.releases.objects
        category = self.data.category
        remotelocation = self.content.path.remote

        if self.should_try_releases:
            for release in releaseobjects or []:
                if ref == release.tag_name:
                    for asset in release.assets or []:
                        files.append(
                            FileInformation(asset.browser_download_url, asset.name, asset.name)
                        )
            if files:
                return files

        if self.content.single:
            for treefile in tree:
                if treefile.filename == self.data.file_name:
                    files.append(
                        FileInformation(
                            treefile.download_url, treefile.full_path, treefile.filename
                        )
                    )
            return files

        if category == "plugin":
            for treefile in tree:
                if treefile.path in ["", "dist"]:
                    if remotelocation == "dist" and not treefile.filename.startswith("dist"):
                        continue
                    if not remotelocation:
                        if not treefile.filename.endswith(".js"):
                            continue
                        if treefile.path != "":
                            continue
                    if not treefile.is_directory:
                        files.append(
                            FileInformation(
                                treefile.download_url, treefile.full_path, treefile.filename
                            )
                        )
            if files:
                return files

        if self.repository_manifest.content_in_root:
            if not self.repository_manifest.filename:
                if category == "theme":
                    tree = filter_content_return_one_of_type(self.tree, "", "yaml", "full_path")

        for path in tree:
            if path.is_directory:
                continue
            if path.full_path.startswith(self.content.path.remote):
                files.append(FileInformation(path.download_url, path.full_path, path.filename))
        return files

    async def release_contents(self, version: str | None = None) -> list[FileInformation] | None:
        """Gather the contents of a release."""
        release = await self.hacs.async_github_api_method(
            method=self.hacs.githubapi.generic,
            endpoint=f"/repos/{self.data.full_name}/releases/tags/{version}",
            raise_exception=False,
        )
        if release is None:
            return None

        return [
            FileInformation(
                url=asset.get("browser_download_url"),
                path=asset.get("name"),
                name=asset.get("name"),
            )
            for asset in release.data.get("assets", [])
        ]

    @concurrent(concurrenttasks=10)
    async def dowload_repository_content(self, content: FileInformation) -> None:
        """Download content."""
        try:
            self.logger.debug("%s Downloading %s", self.string, content.name)

            filecontent = await self.hacs.async_download_file(content.download_url)

            if filecontent is None:
                self.validate.errors.append(f"[{content.name}] was not downloaded.")
                return

            # Save the content of the file.
            if self.content.single or content.path is None:
                local_directory = self.content.path.local

            else:
                _content_path = content.path
                if not self.repository_manifest.content_in_root:
                    _content_path = _content_path.replace(f"{self.content.path.remote}", "")

                local_directory = f"{self.content.path.local}/{_content_path}"
                local_directory = local_directory.split("/")
                del local_directory[-1]
                local_directory = "/".join(local_directory)

            # Check local directory
            pathlib.Path(local_directory).mkdir(parents=True, exist_ok=True)

            local_file_path = (f"{local_directory}/{content.name}").replace("//", "/")

            result = await self.hacs.async_save_file(local_file_path, filecontent)
            if result:
                self.logger.info("%s Download of %s completed", self.string, content.name)
                return
            self.validate.errors.append(f"[{content.name}] was not downloaded.")

        except (
            # lgtm [py/catch-base-exception] pylint: disable=broad-except
            BaseException
        ) as exception:
            self.validate.errors.append(f"Download was not completed [{exception}]")

    async def async_remove_entity_device(self) -> None:
        """Remove the entity device."""
        if (config_entry := self.hacs.configuration.config_entry) is None:
            return

        device_registry: dr.DeviceRegistry = dr.async_get(hass=self.hacs.hass)
        identifier = (DOMAIN, str(self.data.id))

        # Looked up through our own config entry, since identifiers are only
        # guaranteed to be unique within a single config entry.
        for device in dr.async_entries_for_config_entry(device_registry, config_entry.entry_id):
            if identifier in device.identifiers:
                device_registry.async_remove_device(device_id=device.id)
                return

    def version_to_download(self) -> str:
        """Determine which version to download."""
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
        **kwargs,
    ) -> str | None:
        """Get the documentation of the repository."""
        if filename is None:
            return None

        if version is not None:
            target_version = version
        elif self.data.installed:
            target_version = self.data.installed_version or self.data.installed_commit
        else:
            target_version = self.data.last_version or self.data.last_commit or self.ref

        self.logger.debug(
            "%s Getting documentation for version=%s,filename=%s",
            self.string,
            target_version,
            filename,
        )
        if target_version is None:
            return None

        result = await self.hacs.async_download_file(
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
    async def get_hacs_json(self, *, version: str, **kwargs) -> HacsManifest | None:
        """Get the hacs.json file of the repository."""
        if (result := await self.get_hacs_json_raw(version=version)) is None:
            return None
        return HacsManifest.from_dict(result)

    @return_none_on_exception
    async def get_hacs_json_raw(
        self,
        *,
        version: str,
        **kwargs,
    ) -> dict[str, Any] | None:
        """Get the hacs.json file of the repository."""
        self.logger.debug("%s Getting hacs.json for version=%s", self.string, version)
        result = await self.hacs.async_download_file(
            f"https://raw.githubusercontent.com/{self.data.full_name}/{version}/hacs.json",
            nolog=True,
            handle_rate_limit=True,
        )
        return json_loads(result) if result else None

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

    async def _ensure_download_capabilities(self, ref: str | None, **kwargs: Any) -> None:
        """Ensure that the download can be handled."""
        target_manifest: HacsManifest | None = None
        if ref is None:
            if not self.can_download:
                raise HacsException(
                    f"This {self.data.category.value} is not available for download."
                )
            return

        if not ref:
            target_manifest = self.repository_manifest
        else:
            target_manifest = await self.get_hacs_json(version=ref)

        if target_manifest is None:
            raise HacsException(
                f"The version {ref} for this {self.data.category.value} can not be used with HACS."
            )

        if (
            target_manifest.homeassistant is not None
            and self.hacs.core.ha_version < target_manifest.homeassistant
        ):
            raise HacsException(
                f"This version requires Home Assistant {target_manifest.homeassistant} or newer."
            )
        if target_manifest.hacs is not None and self.hacs.version < target_manifest.hacs:
            raise HacsException(f"This version requires HACS {target_manifest.hacs} or newer.")

    async def async_download_repository(self, *, ref: str | None = None, **_) -> None:
        """Download the content of a repository."""
        await self._ensure_download_capabilities(ref)
        self.logger.info("Starting download, %s", ref)
        if self.display_version_or_commit == "version":
            self.hacs.async_dispatch(
                HacsDispatchEvent.REPOSITORY_DOWNLOAD_PROGRESS,
                {"repository": self.data.full_name, "progress": 10},
            )
            if not ref:
                await self.update_repository(force=True)
            else:
                self.ref = ref
            self.data.selected_tag = ref
            self.force_branch = ref is not None
            self.hacs.async_dispatch(
                HacsDispatchEvent.REPOSITORY_DOWNLOAD_PROGRESS,
                {"repository": self.data.full_name, "progress": 20},
            )

        try:
            await self.async_install(version=ref)
        except HacsException as exception:
            raise HacsException(
                f"Downloading {self.data.full_name} with version {ref or self.data.last_version or self.data.last_commit} failed with ({exception})"
            ) from exception
        finally:
            self.data.selected_tag = None
            self.force_branch = False
            self.hacs.async_dispatch(
                HacsDispatchEvent.REPOSITORY_DOWNLOAD_PROGRESS,
                {"repository": self.data.full_name, "progress": False},
            )

    async def async_get_releases(self, *, first: int = 30) -> list[GitHubReleaseModel]:
        """Get the last x releases of a repository."""
        response = await self.hacs.async_github_api_method(
            method=self.hacs.githubapi.repos.releases.list,
            repository=self.data.full_name,
            kwargs={"per_page": 30},
        )
        return response.data

    async def async_set_last_commits(self) -> None:
        """Set the last commit for the repository."""
        response = await self.hacs.async_github_api_method(
            method=self.hacs.githubapi.generic,
            endpoint=f"/repos/{self.data.full_name}/branches/{self.data.default_branch}",
        )
        if response is not None and response.data:
            last_commit = response.data["commit"]["sha"]
            self.data.last_commit = last_commit[:7]
