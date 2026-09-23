"""Data handler for the Community store."""

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any

from homeassistant.core import Event, callback
from homeassistant.exceptions import HomeAssistantError

from ..base import StoreManager
from ..const import LEGACY_HACS_REPOSITORY_ID
from ..enums import StoreSignal
from ..repositories.base import TOPIC_FILTER, Repository, RepositoryManifest
from .logger import LOGGER
from .path import is_safe
from .storage import (
    async_load_from_storage,
    async_load_legacy_data,
    async_save_to_storage,
)

EXPORTED_BASE_DATA: tuple[tuple[str, Any], ...] = (
    ("new", False),
    ("full_name", ""),
)

EXPORTED_REPOSITORY_DATA: tuple[tuple[str, Any], ...] = (
    *EXPORTED_BASE_DATA,
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

EXPORTED_DOWNLOADED_REPOSITORY_DATA: tuple[tuple[str, Any], ...] = (
    *EXPORTED_REPOSITORY_DATA,
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


class StoreData:
    """Handles the stored data of the store."""

    def __init__(self, store: StoreManager) -> None:
        """Initialize."""
        self.logger = LOGGER
        self.store = store
        self.content: dict[str, Any] = {}

    async def async_force_write(self, _: Event | None = None) -> None:
        """Force write."""
        await self.async_write(force=True)

    async def async_write(self, force: bool = False) -> None:
        """Write content to the store files."""
        if not force and self.store.system.disabled:
            return

        self.logger.debug("Saving data")

        await async_save_to_storage(
            self.store.hass,
            "common",
            {
                "archived_repositories": self.store.common.archived_repositories,
                "renamed_repositories": self.store.common.renamed_repositories,
                "ignored_repositories": self.store.common.ignored_repositories,
            },
        )
        await self._async_store_content_and_repos()

    async def _async_store_content_and_repos(
        self, _: Event | None = None
    ) -> None:  # bb: ignore
        """Store the main repos file and each repo that is out of date."""
        # Repositories
        self.content = {}
        for repository in self.store.repositories.list_all:
            if repository.data.category in self.store.common.categories:
                self.async_store_repository_data(repository)

        await async_save_to_storage(self.store.hass, "repositories", self.content)
        for event in (StoreSignal.REPOSITORY, StoreSignal.CONFIG):
            self.store.async_dispatch(event, {})

    @callback
    def async_store_repository_data(self, repository: Repository) -> None:
        """Store the repository data."""
        data: dict[str, Any] = {
            "repository_manifest": repository.repository_manifest.manifest
        }

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

    async def restore(self) -> bool:
        """Restore saved data."""
        self.store.status.new = False
        repositories: dict[str, Any] = {}
        common: dict[str, Any] = {}

        with contextlib.suppress(HomeAssistantError):
            common = await async_load_from_storage(self.store.hass, "common") or {}

        try:
            repositories = await async_load_from_storage(
                self.store.hass, "repositories"
            )
            if not repositories and (
                data := await async_load_legacy_data(self.store.hass)
            ):
                for category, entries in data.get("repositories", {}).items():
                    for repository in entries:
                        repositories[repository["id"]] = {
                            "category": category,
                            **repository,
                        }

        except HomeAssistantError as exception:
            LOGGER.error(
                "Could not read %s, restore the file from a backup - %s",
                self.store.hass.config.path(".storage/store.repositories"),
                exception,
            )
            return False

        if not common and not repositories:
            # Assume new install
            self.store.status.new = True
            return True

        self.logger.info("Restore started")

        self.store.common.archived_repositories = set()
        self.store.common.ignored_repositories = set()
        self.store.common.renamed_repositories = {}

        # Clear out doubble renamed values
        renamed = common.get("renamed_repositories", {})
        for entry in renamed:
            value = renamed.get(entry)
            if value not in renamed:
                self.store.common.renamed_repositories[entry] = value

        # Clear out doubble archived values
        for entry in common.get("archived_repositories", set()):
            if entry not in self.store.common.archived_repositories:
                self.store.common.archived_repositories.add(entry)

        # Clear out doubble ignored values
        for entry in common.get("ignored_repositories", set()):
            if entry not in self.store.common.ignored_repositories:
                self.store.common.ignored_repositories.add(entry)

        try:
            await self.register_unknown_repositories(repositories)

            for entry, repo_data in repositories.items():
                if entry == "0":
                    # Ignore repositories with ID 0
                    self.logger.debug(
                        "Found repository with ID %s - %s",
                        entry,
                        repo_data,
                    )
                    continue
                self.async_restore_repository(entry, repo_data)

            self.logger.info("Restore done")
        except Exception as exception:
            self.logger.critical("[%s] Restore failed", exception, exc_info=exception)
            return False
        return True

    async def register_unknown_repositories(
        self, repositories: dict[str, dict[str, Any]], category: str | None = None
    ) -> None:
        """Registry any unknown repositories."""
        for repo_idx, (entry, repo_data) in enumerate(repositories.items()):
            # async_register_repository is awaited in a loop
            # since its unlikely to ever suspend at startup
            repo_category = repo_data.get("category", category)
            if (
                entry in ("0", LEGACY_HACS_REPOSITORY_ID)
                or repo_category is None
                or self.store.repositories.is_registered(repository_id=entry)
            ):
                continue
            await self.store.async_register_repository(
                repository_full_name=repo_data["full_name"],
                category=repo_category,
                check=False,
                repository_id=entry,
            )
            if repo_idx % 100 == 0:
                # yield to avoid blocking the event loop
                await asyncio.sleep(0)

    @callback
    def async_restore_repository(
        self, entry: str, repository_data: dict[str, Any]
    ) -> None:
        """Restore repository."""
        if entry == LEGACY_HACS_REPOSITORY_ID:
            # The store is part of Home Assistant, it does not manage itself
            return

        repository: Repository | None = None
        if full_name := repository_data.get("full_name"):
            repository = self.store.repositories.get_by_full_name(full_name)
        if not repository:
            repository = self.store.repositories.get_by_id(entry)
        if not repository:
            return

        try:
            self.store.repositories.set_repository_id(repository, entry)
        except ValueError as exception:
            self.logger.warning("Duplicate IDs %s", exception)
            return

        # Restore repository attributes
        repository.data.authors = repository_data.get("authors", [])
        repository.data.description = repository_data.get("description", "")
        repository.data.downloads = repository_data.get("downloads", 0)
        repository.data.last_updated = repository_data.get("last_updated", 0)
        repository.data.etag_repository = repository_data.get("etag_repository")
        repository.data.topics = [
            topic
            for topic in repository_data.get("topics", [])
            if topic not in TOPIC_FILTER
        ]
        repository.data.domain = repository_data.get("domain")
        repository.data.stargazers_count = repository_data.get(
            "stargazers_count"
        ) or repository_data.get("stars", 0)
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

        repository.repository_manifest = RepositoryManifest.from_dict(
            repository_data.get("manifest")
            or repository_data.get("repository_manifest")
            or {}
        )

        if repository.data.prerelease == repository.data.last_version:
            repository.data.prerelease = None

        if repository.localpath is not None and is_safe(
            self.store, repository.localpath
        ):
            # Set local path
            repository.content.path.local = repository.localpath

        if repository.data.installed:
            repository.data.first_install = False
