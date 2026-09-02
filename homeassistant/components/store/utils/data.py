"""Data handler for HACS."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from ..base import HacsBase
from ..const import HACS_REPOSITORY_ID
from ..enums import HacsDisabledReason, HacsDispatchEvent
from ..repositories.base import TOPIC_FILTER, HacsManifest, HacsRepository
from .logger import LOGGER
from .path import is_safe
from .store import async_load_from_store, async_save_to_store

EXPORTED_BASE_DATA = (
    ("new", False),
    ("full_name", ""),
)

EXPORTED_REPOSITORY_DATA = EXPORTED_BASE_DATA + (
    ("authors", []),
    ("category", ""),
    ("description", ""),
    ("domain", None),
    ("downloads", 0),
    ("etag_repository", None),
    ("hide", False),
    ("last_updated", 0),
    ("new", False),
    ("stargazers_count", 0),
    ("topics", []),
)

EXPORTED_DOWNLOADED_REPOSITORY_DATA = EXPORTED_REPOSITORY_DATA + (
    ("archived", False),
    ("config_flow", False),
    ("default_branch", None),
    ("first_install", False),
    ("installed_commit", None),
    ("installed", False),
    ("last_commit", None),
    ("last_version", None),
    ("manifest_name", None),
    ("open_issues", 0),
    ("prerelease", None),
    ("published_tags", []),
    ("releases", False),
    ("selected_tag", None),
    ("show_beta", False),
)


class HacsData:
    """HacsData class."""

    def __init__(self, hacs: HacsBase):
        """Initialize."""
        self.logger = LOGGER
        self.hacs = hacs
        self.content = {}

    async def async_force_write(self, _=None):
        """Force write."""
        await self.async_write(force=True)

    async def async_write(self, force: bool = False) -> None:
        """Write content to the store files."""
        if not force and self.hacs.system.disabled:
            return

        self.logger.debug("<HacsData async_write> Saving data")

        # Hacs
        await async_save_to_store(
            self.hacs.hass,
            "hacs",
            {
                "archived_repositories": self.hacs.common.archived_repositories,
                "renamed_repositories": self.hacs.common.renamed_repositories,
                "ignored_repositories": self.hacs.common.ignored_repositories,
            },
        )
        await self._async_store_experimental_content_and_repos()
        await self._async_store_content_and_repos()

    async def _async_store_content_and_repos(self, _=None):  # bb: ignore
        """Store the main repos file and each repo that is out of date."""
        # Repositories
        self.content = {}
        for repository in self.hacs.repositories.list_all:
            if repository.data.category in self.hacs.common.categories:
                self.async_store_repository_data(repository)

        await async_save_to_store(self.hacs.hass, "repositories", self.content)
        for event in (HacsDispatchEvent.REPOSITORY, HacsDispatchEvent.CONFIG):
            self.hacs.async_dispatch(event, {})

    async def _async_store_experimental_content_and_repos(self, _=None):
        """Store the main repos file and each repo that is out of date."""
        # Repositories
        self.content = {}
        for repository in self.hacs.repositories.list_all:
            if repository.data.category in self.hacs.common.categories:
                self.async_store_experimental_repository_data(repository)

        await async_save_to_store(self.hacs.hass, "data", {"repositories": self.content})

    @callback
    def async_store_repository_data(self, repository: HacsRepository) -> dict:
        """Store the repository data."""
        data = {"repository_manifest": repository.repository_manifest.manifest}

        for key, default in (
            EXPORTED_DOWNLOADED_REPOSITORY_DATA
            if repository.data.installed
            else EXPORTED_REPOSITORY_DATA
        ):
            if (value := getattr(repository.data, key, default)) != default:
                data[key] = value

        if repository.data.installed_version:
            data["version_installed"] = repository.data.installed_version
        if repository.data.last_fetched:
            data["last_fetched"] = repository.data.last_fetched.timestamp()

        self.content[str(repository.data.id)] = data

    @callback
    def async_store_experimental_repository_data(self, repository: HacsRepository) -> None:
        """Store the experimental repository data for non downloaded repositories."""
        data = {}
        self.content.setdefault(repository.data.category, [])

        if repository.data.installed:
            data["repository_manifest"] = repository.repository_manifest.manifest
            for key, default in EXPORTED_DOWNLOADED_REPOSITORY_DATA:
                if (value := getattr(repository.data, key, default)) != default:
                    data[key] = value

            if repository.data.installed_version:
                data["version_installed"] = repository.data.installed_version
            if repository.data.last_fetched:
                data["last_fetched"] = repository.data.last_fetched.timestamp()
        else:
            for key, default in EXPORTED_BASE_DATA:
                if (value := getattr(repository.data, key, default)) != default:
                    data[key] = value

        self.content[repository.data.category].append({"id": str(repository.data.id), **data})

    async def restore(self):
        """Restore saved data."""
        self.hacs.status.new = False
        repositories = {}
        hacs = {}

        try:
            hacs = await async_load_from_store(self.hacs.hass, "hacs") or {}
        except HomeAssistantError:
            pass

        try:
            repositories = await async_load_from_store(self.hacs.hass, "repositories")
            if not repositories and (data := await async_load_from_store(self.hacs.hass, "data")):
                for category, entries in data.get("repositories", {}).items():
                    for repository in entries:
                        repositories[repository["id"]] = {"category": category, **repository}

        except HomeAssistantError as exception:
            self.hacs.log.error(
                "Could not read %s, restore the file from a backup - %s",
                self.hacs.hass.config.path(".storage/hacs.data"),
                exception,
            )
            self.hacs.disable_hacs(HacsDisabledReason.RESTORE)
            return False

        if not hacs and not repositories:
            # Assume new install
            self.hacs.status.new = True
            return True

        self.logger.info("<HacsData restore> Restore started")

        # Hacs
        self.hacs.common.archived_repositories = set()
        self.hacs.common.ignored_repositories = set()
        self.hacs.common.renamed_repositories = {}

        # Clear out doubble renamed values
        renamed = hacs.get("renamed_repositories", {})
        for entry in renamed:
            value = renamed.get(entry)
            if value not in renamed:
                self.hacs.common.renamed_repositories[entry] = value

        # Clear out doubble archived values
        for entry in hacs.get("archived_repositories", set()):
            if entry not in self.hacs.common.archived_repositories:
                self.hacs.common.archived_repositories.add(entry)

        # Clear out doubble ignored values
        for entry in hacs.get("ignored_repositories", set()):
            if entry not in self.hacs.common.ignored_repositories:
                self.hacs.common.ignored_repositories.add(entry)

        try:
            await self.register_unknown_repositories(repositories)

            for entry, repo_data in repositories.items():
                if entry == "0":
                    # Ignore repositories with ID 0
                    self.logger.debug(
                        "<HacsData restore> Found repository with ID %s - %s", entry, repo_data
                    )
                    continue
                self.async_restore_repository(entry, repo_data)

            self.logger.info("<HacsData restore> Restore done")
        except (
            # lgtm [py/catch-base-exception] pylint: disable=broad-except
            BaseException
        ) as exception:
            self.logger.critical(
                "<HacsData restore> [%s] Restore Failed!", exception, exc_info=exception
            )
            return False
        return True

    async def register_unknown_repositories(
        self, repositories: dict[str, dict[str, Any]], category: str | None = None
    ):
        """Registry any unknown repositories."""
        for repo_idx, (entry, repo_data) in enumerate(repositories.items()):
            # async_register_repository is awaited in a loop
            # since its unlikely to ever suspend at startup
            if (
                entry == "0"
                or repo_data.get("category", category) is None
                or self.hacs.repositories.is_registered(repository_id=entry)
            ):
                continue
            await self.hacs.async_register_repository(
                repository_full_name=repo_data["full_name"],
                category=repo_data.get("category", category),
                check=False,
                repository_id=entry,
            )
            if repo_idx % 100 == 0:
                # yield to avoid blocking the event loop
                await asyncio.sleep(0)

    @callback
    def async_restore_repository(self, entry: str, repository_data: dict[str, Any]):
        """Restore repository."""
        repository: HacsRepository | None = None
        if full_name := repository_data.get("full_name"):
            repository = self.hacs.repositories.get_by_full_name(full_name)
        if not repository:
            repository = self.hacs.repositories.get_by_id(entry)
        if not repository:
            return

        try:
            self.hacs.repositories.set_repository_id(repository, entry)
        except ValueError as exception:
            self.logger.warning("<HacsData async_restore_repository> duplicate IDs %s", exception)
            return

        # Restore repository attributes
        repository.data.authors = repository_data.get("authors", [])
        repository.data.description = repository_data.get("description", "")
        repository.data.downloads = repository_data.get("downloads", 0)
        repository.data.last_updated = repository_data.get("last_updated", 0)
        if self.hacs.system.generator:
            repository.data.etag_releases = repository_data.get("etag_releases")
            repository.data.open_issues = repository_data.get("open_issues", 0)
        repository.data.etag_repository = repository_data.get("etag_repository")
        repository.data.topics = [
            topic for topic in repository_data.get("topics", []) if topic not in TOPIC_FILTER
        ]
        repository.data.domain = repository_data.get("domain")
        repository.data.stargazers_count = repository_data.get(
            "stargazers_count"
        ) or repository_data.get("stars", 0)
        repository.releases.last_release = repository_data.get("last_release_tag")
        repository.data.releases = repository_data.get("releases", False)
        repository.data.installed = repository_data.get("installed", False)
        repository.data.new = repository_data.get("new", False)
        repository.data.selected_tag = repository_data.get("selected_tag")
        repository.data.show_beta = repository_data.get("show_beta", False)
        repository.data.last_version = repository_data.get("last_version")
        repository.data.prerelease = repository_data.get("prerelease")
        repository.data.last_commit = repository_data.get("last_commit")
        repository.data.installed_version = repository_data.get("version_installed")
        repository.data.installed_commit = repository_data.get("installed_commit")
        repository.data.manifest_name = repository_data.get("manifest_name")

        if last_fetched := repository_data.get("last_fetched"):
            repository.data.last_fetched = datetime.fromtimestamp(last_fetched, UTC)

        repository.repository_manifest = HacsManifest.from_dict(
            repository_data.get("manifest") or repository_data.get("repository_manifest") or {}
        )

        if repository.data.prerelease == repository.data.last_version:
            repository.data.prerelease = None

        if repository.localpath is not None and is_safe(self.hacs, repository.localpath):
            # Set local path
            repository.content.path.local = repository.localpath

        if repository.data.installed:
            repository.data.first_install = False

        if entry == HACS_REPOSITORY_ID:
            repository.data.installed_version = self.hacs.version
            repository.data.installed = True
