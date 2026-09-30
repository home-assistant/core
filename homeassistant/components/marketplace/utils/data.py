"""Data handler for the Marketplace."""

import asyncio
import contextlib
from datetime import UTC, datetime
import os
from typing import Any

from homeassistant.core import Event, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from ..base import MarketplaceManager
from ..const import DOMAIN, LEGACY_HACS_REPOSITORY_ID, RESTART_ISSUE_PREFIX
from ..enums import DisabledReason, MarketplaceSignal, RepositoryCategory
from ..migration import async_forget_retired_repositories
from ..repositories.base import TOPIC_FILTER, Repository, RepositoryManifest
from .identity import one_stored_entry_per_name
from .logger import LOGGER
from .path import is_safe
from .storage import async_load_from_storage, async_save_to_storage

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
    ("stargazers_count", 0),
    ("topics", []),
)

EXPORTED_INSTALLED_REPOSITORY_DATA: tuple[tuple[str, Any], ...] = (
    *EXPORTED_REPOSITORY_DATA,
    ("archived", False),
    ("config_flow", False),
    ("default_branch", None),
    ("directory", None),
    ("file_name", ""),
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


class MarketplaceData:
    """Handles the stored data of the Marketplace."""

    def __init__(self, marketplace: MarketplaceManager) -> None:
        """Initialize."""
        self.logger = LOGGER
        self.marketplace = marketplace
        self.content: dict[str, Any] = {}
        # The ids of installs that wait for a restart, known while restoring
        self._waiting_for_restart: set[str] = set()
        # Written back as they were, dropping them would lose track of installs
        self._unrestorable: dict[str, dict[str, Any]] = {}

    async def async_force_write(self, _: Event | None = None) -> None:
        """Force write."""
        await self.async_write(force=True)

    async def async_write(self, force: bool = False) -> None:
        """Write content to the storage files."""
        # Only an unloaded Marketplace stops saving, an install works while
        # GitHub is out of reach and has to be kept.
        if (
            not force
            and self.marketplace.system.disabled_reason is DisabledReason.REMOVED
        ):
            return

        self.logger.debug("Saving data")

        await async_save_to_storage(
            self.marketplace.hass,
            "common",
            # Copies, the data is encoded in the executor while the loop moves on
            {
                "archived_repositories": set(
                    self.marketplace.common.archived_repositories
                ),
                "renamed_repositories": dict(
                    self.marketplace.common.renamed_repositories
                ),
                "ignored_repositories": set(
                    self.marketplace.common.ignored_repositories
                ),
                "custom_repositories": set(self.marketplace.common.custom_repositories),
            },
        )
        await self._async_store_repositories()

    async def _async_store_repositories(self) -> None:
        """Store the repositories file, and tell the panel."""
        self.content = {}
        for repository in self.marketplace.repositories.list_all:
            if repository.data.category in self.marketplace.common.categories:
                self.async_store_repository_data(repository)
        for entry, repo_data in self._unrestorable.items():
            self.content.setdefault(entry, repo_data)

        await async_save_to_storage(self.marketplace.hass, "repositories", self.content)
        for event in (MarketplaceSignal.REPOSITORY, MarketplaceSignal.CONFIG):
            self.marketplace.async_dispatch(event, {})

    @callback
    def async_store_repository_data(self, repository: Repository) -> None:
        """Store the repository data."""
        # Copies, the data is encoded in the executor while the loop moves on
        data: dict[str, Any] = {
            "repository_manifest": dict(repository.repository_manifest.manifest)
        }

        for key, default in (
            EXPORTED_INSTALLED_REPOSITORY_DATA
            if repository.data.installed
            else EXPORTED_REPOSITORY_DATA
        ):
            if (value := getattr(repository.data, key, default)) != default:
                data[key] = value.copy() if isinstance(value, list | dict) else value

        if repository.data.installed_version:
            data["version_installed"] = repository.data.installed_version
        if repository.data.last_fetched:
            data["last_fetched"] = repository.data.last_fetched.timestamp()

        self.content[str(repository.data.id)] = data

    async def _async_load(self, key: str) -> dict[str, Any] | None:
        """Load a storage file, None when it can not be read."""
        path = self.marketplace.hass.config.path(f".storage/marketplace.{key}")
        try:
            data = await async_load_from_storage(self.marketplace.hass, key)
        # The error names the file, it can be one of the custom integration too
        except HomeAssistantError as exception:
            self._log_unreadable(str(exception))
            return None
        # What the storage helper raises for a version it does not know
        except NotImplementedError:
            self._log_unreadable(f"{path} has a storage version it does not know")
            return None

        if data is None:
            return {}
        if not isinstance(data, dict):
            self._log_unreadable(f"{path} does not hold an object")
            return None
        return data

    def _log_unreadable(self, reason: str) -> None:
        """Log that stored data can not be read, the reason names the file."""
        LOGGER.error(
            "Could not read the stored data of the Marketplace, restore the file"
            " from a backup - %s",
            reason,
        )

    async def restore(self) -> bool:
        """Restore saved data."""
        self.marketplace.status.new = False
        # Taken as empty, the next write would make the loss permanent
        if (common := await self._async_load("common")) is None:
            return False
        if (repositories := await self._async_load("repositories")) is None:
            return False

        repositories = {
            entry: repo_data
            for entry, repo_data in repositories.items()
            if self._is_restorable(entry, repo_data)
        }

        config_entry = self.marketplace.configuration.config_entry
        assert config_entry is not None
        async_forget_retired_repositories(
            self.marketplace.hass, config_entry, repositories
        )

        if not common and not repositories:
            # Nothing stored, a first setup
            self.marketplace.status.new = True
            return True

        self.logger.info("Restore started")

        renamed = common.get("renamed_repositories", {})
        # A rename to a name that was renamed again is dropped, lookups take one step
        self.marketplace.common.renamed_repositories = {
            old: new for old, new in renamed.items() if new not in renamed
        }
        self.marketplace.common.archived_repositories = set(
            common.get("archived_repositories", [])
        )
        self.marketplace.common.ignored_repositories = set(
            common.get("ignored_repositories", [])
        )
        self.marketplace.common.custom_repositories = set(
            common.get("custom_repositories", [])
        )

        repositories = one_stored_entry_per_name(repositories)

        # A reload does not load the installed code, only a restart does, and
        # a restart removes these repairs
        self._waiting_for_restart = {
            issue_id.removeprefix(RESTART_ISSUE_PREFIX).split("_", maxsplit=1)[0]
            for domain, issue_id in ir.async_get(self.marketplace.hass).issues
            if domain == DOMAIN and issue_id.startswith(RESTART_ISSUE_PREFIX)
        }

        try:
            await self.register_unknown_repositories(repositories)

            for entry, repo_data in repositories.items():
                if entry == "0":
                    self.logger.debug(
                        "Found repository with ID %s - %s",
                        entry,
                        repo_data,
                    )
                    continue
                self._async_restore_or_skip(entry, repo_data)

            await self._async_forget_deleted_installs()
            self.logger.info("Restore done")
        except Exception as exception:
            self.logger.critical("[%s] Restore failed", exception, exc_info=exception)
            return False
        return True

    def _is_restorable(self, entry: str, repo_data: Any) -> bool:
        """Return if a stored repository has the shape the Marketplace wrote."""
        if isinstance(repo_data, dict) and isinstance(repo_data.get("full_name"), str):
            return True

        self.logger.warning("Skipping stored repository %s, it is not valid", entry)
        return False

    @callback
    def _async_restore_or_skip(self, entry: str, repo_data: dict[str, Any]) -> None:
        """Restore a repository, one that can not be restored stops no others."""
        try:
            self.async_restore_repository(entry, repo_data)
        except Exception:
            self.logger.warning(
                "Skipping stored repository %s, it can not be restored",
                entry,
                exc_info=True,
            )
            self._unrestorable[entry] = repo_data
            if repository := self.marketplace.repositories.get_by_id(entry):
                self.marketplace.repositories.unregister(repository)

    def _install_path(self, repository: Repository) -> str | None:
        """Return what an installed repository has on disk, None when not known."""
        if not (local := repository.content.path.local):
            return None

        # Templates share one folder, only their file is their own
        if repository.data.category == RepositoryCategory.TEMPLATE:
            if not repository.data.file_name:
                return None
            return os.path.join(local, repository.data.file_name)

        # Without a domain, the folder of an integration is not known
        if (
            repository.data.category == RepositoryCategory.INTEGRATION
            and not repository.data.domain
        ):
            return None

        # A shared folder says nothing about the files of one repository
        if not is_safe(self.marketplace, local):
            return None

        return local

    async def _async_forget_deleted_installs(self) -> None:
        """Mark what was deleted by hand as no longer installed."""
        installed = list(self.marketplace.repositories.list_installed)

        # A symlink counts even when what it points at is not there right now,
        # for example a network share that is not mounted yet
        def _deleted() -> list[Repository]:
            return [
                repository
                for repository in installed
                if (path := self._install_path(repository)) is not None
                and not os.path.lexists(path)
            ]

        for repository in await self.marketplace.hass.async_add_executor_job(_deleted):
            self.logger.info(
                "%s is no longer on disk, it is no longer installed",
                repository.data.full_name,
            )
            repository.data.installed = False
            repository.data.installed_version = None
            repository.data.installed_commit = None
            await repository.async_remove_entity_device()

    async def register_unknown_repositories(
        self, repositories: dict[str, dict[str, Any]], category: str | None = None
    ) -> None:
        """Register the stored repositories the catalog does not list."""
        for repo_idx, (entry, repo_data) in enumerate(repositories.items()):
            repo_category = repo_data.get("category", category)
            if (
                entry in ("0", LEGACY_HACS_REPOSITORY_ID)
                or repo_category is None
                or self.marketplace.repositories.is_registered(repository_id=entry)
                # Known under another id, it takes over the new one later on
                or self.marketplace.repositories.is_registered(
                    repository_full_name=repo_data["full_name"].lower()
                )
            ):
                continue
            await self.marketplace.async_register_repository(
                repository_full_name=repo_data["full_name"],
                category=repo_category,
                check=False,
                repository_id=entry,
            )
            # Registering rarely suspends at startup, the loop gets a turn now and then
            if repo_idx % 100 == 0:
                await asyncio.sleep(0)

    @callback
    def async_restore_repository(
        self, entry: str, repository_data: dict[str, Any]
    ) -> None:
        """Restore repository."""
        if entry == LEGACY_HACS_REPOSITORY_ID:
            # The Marketplace is part of Home Assistant, it does not manage itself
            return

        repository: Repository | None = None
        if full_name := repository_data.get("full_name"):
            repository = self.marketplace.repositories.get_by_full_name(full_name)
        if not repository:
            repository = self.marketplace.repositories.get_by_id(entry)
        if not repository:
            return

        self.marketplace.async_set_repository_id(repository, entry)

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
        repository.data.config_flow = repository_data.get("config_flow", False)
        repository.pending_restart = entry in self._waiting_for_restart
        repository.data.file_name = repository_data.get(
            "file_name", repository.data.file_name
        )
        repository.data.directory = repository_data.get("directory")
        # Stored without a folder, the install went to the folder of its name then
        if repository.data.installed and not repository.data.directory:
            if repository.data.category == RepositoryCategory.PLUGIN and full_name:
                repository.data.directory = full_name.rsplit("/", maxsplit=1)[-1]
            elif (
                repository.data.category == RepositoryCategory.THEME
                and repository.data.file_name
            ):
                repository.data.directory = repository.data.file_name.replace(
                    ".yaml", ""
                )

        # Without it, the next catalog fetch takes the data over right away
        if last_fetched := repository_data.get("last_fetched"):
            with contextlib.suppress(TypeError, ValueError, OverflowError):
                repository.data.last_fetched = datetime.fromtimestamp(last_fetched, UTC)

        manifest = (
            repository_data.get("manifest")
            or repository_data.get("repository_manifest")
            or {}
        )
        repository.repository_manifest = RepositoryManifest.from_dict(
            manifest if isinstance(manifest, dict) else {}
        )

        # Stored before file names were, a template names its file in hacs.json
        if (
            repository.data.category == RepositoryCategory.TEMPLATE
            and not repository.data.file_name
        ):
            repository.data.file_name = repository.repository_manifest.filename or ""

        if repository.data.prerelease == repository.data.last_version:
            repository.data.prerelease = None

        # Every removal checks it is safe again, resolving here would block
        if repository.localpath is not None:
            repository.content.path.local = repository.localpath
