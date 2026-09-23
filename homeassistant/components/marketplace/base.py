"""Base classes for the Marketplace."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
import gzip
import math
import os
import shutil
from typing import TYPE_CHECKING, Any, Literal, overload

from aiogithubapi import (
    GitHubAPI,
    GitHubAuthenticationException,
    GitHubException,
    GitHubNotModifiedException,
    GitHubRatelimitException,
)
from aiohttp.client import ClientSession, ClientTimeout
from awesomeversion import AwesomeVersion

from homeassistant.components.persistent_notification import (
    async_create as async_create_persistent_notification,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.util import dt as dt_util

from .const import (
    COUNTRY_ALL,
    DOMAIN,
    LEGACY_HACS_INTEGRATION_REPOSITORY,
    MAX_DOWNLOAD_SIZE,
    TV,
)
from .coordinator import MarketplaceUpdateCoordinator
from .data_client import CatalogClient
from .enums import (
    DisabledReason,
    LovelaceMode,
    MarketplaceSignal,
    MarketplaceStage,
    RepositoryCategory,
)
from .exceptions import (
    AppRepositoryError,
    CoreRepositoryError,
    ExecutionInProgressError,
    ExpectedError,
    MarketplaceError,
    NotModifiedError,
    RepositoryArchivedError,
    RepositoryExistsError,
)
from .repositories import REPOSITORY_CLASSES
from .repositories.base import (
    REPOSITORY_KEYS_TO_EXPORT,
    REPOSITORY_MANIFEST_KEYS_TO_EXPORT,
)
from .utils.file_system import async_exists
from .utils.logger import LOGGER
from .utils.queue_manager import QueueManager
from .utils.storage import async_load_from_storage, async_save_to_storage

if TYPE_CHECKING:
    from .repositories.base import Repository
    from .utils.data import MarketplaceData


def _declared_size(headers: Mapping[str, str]) -> int:
    """Return the size a response declares, 0 when it declares none."""
    length = headers.get("Content-Length", "")
    return int(length) if length.isdigit() else 0


@dataclass
class RemovedRepository:
    """Removed repository."""

    repository: str | None = None
    reason: str | None = None
    link: str | None = None
    removal_type: str | None = None  # archived, not_compliant, critical, dev, broken
    acknowledged: bool = False

    def update_data(self, data: dict[str, Any]) -> None:
        """Update data of the repository."""
        for key, value in data.items():
            if value is None:
                continue
            if key in (
                "reason",
                "link",
                "removal_type",
                "acknowledged",
            ):
                setattr(self, key, value)

    def to_json(self) -> dict[str, Any]:
        """Return a JSON representation of the data."""
        return {
            "repository": self.repository,
            "reason": self.reason,
            "link": self.link,
            "removal_type": self.removal_type,
            "acknowledged": self.acknowledged,
        }


@dataclass
class MarketplaceConfiguration:
    """Configuration of the Marketplace."""

    appdaemon_path: str = "appdaemon/apps/"
    appdaemon: bool = False
    config_entry: ConfigEntry | None = None
    country: str = COUNTRY_ALL
    debug: bool = False
    plugin_path: str = "www/community/"
    python_script_path: str = "python_scripts/"
    python_script: bool = False
    release_limit: int = 5
    theme_path: str = "themes/"
    theme: bool = False
    token: str | None = None

    def to_json(self) -> dict[str, Any]:
        """Return a json representation of the configuration."""
        return asdict(self)

    def update_from_dict(self, data: dict[str, Any]) -> None:
        """Set attributes from dicts."""
        if not isinstance(data, dict):
            raise MarketplaceError("Configuration is not valid.")

        for key, value in data.items():
            if key in {"experimental", "netdaemon", "release_limit", "debug"}:
                continue
            setattr(self, key, value)


class MarketplaceCore:
    """Core info the Marketplace needs."""

    config_path: str = ""
    lovelace_mode: LovelaceMode = LovelaceMode.YAML


@dataclass
class MarketplaceCommon:
    """Common data of the Marketplace."""

    categories: set[RepositoryCategory] = field(default_factory=set)
    renamed_repositories: dict[str, str] = field(default_factory=dict)
    archived_repositories: set[str] = field(default_factory=set)
    ignored_repositories: set[str] = field(default_factory=set)
    skip: set[str] = field(default_factory=set)


@dataclass
class MarketplaceStatus:
    """Status of the Marketplace."""

    startup: bool = True
    new: bool = False
    created_www_directory: bool = False


@dataclass
class MarketplaceSystem:
    """System info of the Marketplace."""

    disabled_reason: DisabledReason | None = None
    stage: MarketplaceStage = MarketplaceStage.SETUP

    @property
    def disabled(self) -> bool:
        """Return if the Marketplace is disabled."""
        return self.disabled_reason is not None


@dataclass
class Repositories:
    """The repositories the Marketplace knows about."""

    _default_repositories: set[str] = field(default_factory=set)
    _repositories: set[Repository] = field(default_factory=set)
    _repositories_by_full_name: dict[str, Repository] = field(default_factory=dict)
    _repositories_by_id: dict[str, Repository] = field(default_factory=dict)
    _removed_repositories_by_full_name: dict[str, RemovedRepository] = field(
        default_factory=dict
    )

    @property
    def list_all(self) -> list[Repository]:
        """Return a list of repositories."""
        return list(self._repositories)

    @property
    def list_removed(self) -> list[RemovedRepository]:
        """Return a list of removed repositories."""
        return list(self._removed_repositories_by_full_name.values())

    @property
    def list_downloaded(self) -> list[Repository]:
        """Return a list of downloaded repositories."""
        return [repo for repo in self._repositories if repo.data.installed]

    def category_downloaded(self, category: RepositoryCategory) -> bool:
        """Check if a given category has been downloaded."""
        for repository in self.list_downloaded:
            if repository.data.category == category:
                return True
        return False

    def register(self, repository: Repository, default: bool = False) -> None:
        """Register a repository."""
        repo_id = str(repository.data.id)

        if repo_id == "0":
            return

        if registered_repo := self._repositories_by_id.get(repo_id):
            if registered_repo.data.full_name == repository.data.full_name:
                return

            self.unregister(registered_repo)

            registered_repo.data.full_name = repository.data.full_name
            registered_repo.data.new = False
            repository = registered_repo

        if repository not in self._repositories:
            self._repositories.add(repository)

        self._repositories_by_id[repo_id] = repository
        self._repositories_by_full_name[repository.data.full_name_lower] = repository

        if default:
            self.mark_default(repository)

    def unregister(self, repository: Repository) -> None:
        """Unregister a repository."""
        repo_id = str(repository.data.id)

        if repo_id == "0":
            return

        if not self.is_registered(repository_id=repo_id):
            return

        if self.is_default(repo_id):
            self._default_repositories.remove(repo_id)

        if repository in self._repositories:
            self._repositories.remove(repository)

        self._repositories_by_id.pop(repo_id, None)
        self._repositories_by_full_name.pop(repository.data.full_name_lower, None)

    def mark_default(self, repository: Repository) -> None:
        """Mark a repository as default."""
        repo_id = str(repository.data.id)

        if repo_id == "0":
            return

        if not self.is_registered(repository_id=repo_id):
            return

        self._default_repositories.add(repo_id)

    def set_repository_id(self, repository: Repository, repo_id: str) -> None:
        """Update a repository id."""
        existing_repo_id = str(repository.data.id)
        if existing_repo_id == repo_id:
            return
        if existing_repo_id != "0":
            raise ValueError(
                f"The repo id for {repository.data.full_name_lower} "
                f"is already set to {existing_repo_id}"
            )
        repository.data.id = repo_id
        self.register(repository)

    def is_default(self, repository_id: str | None = None) -> bool:
        """Check if a repository is default."""
        if not repository_id:
            return False
        return repository_id in self._default_repositories

    def is_registered(
        self,
        repository_id: str | None = None,
        repository_full_name: str | None = None,
    ) -> bool:
        """Check if a repository is registered."""
        if repository_id is not None:
            return repository_id in self._repositories_by_id
        if repository_full_name is not None:
            return repository_full_name in self._repositories_by_full_name
        return False

    def is_downloaded(
        self,
        repository_id: str | None = None,
        repository_full_name: str | None = None,
    ) -> bool:
        """Check if a repository is registered."""
        if repository_id is not None:
            repo = self.get_by_id(repository_id)
        if repository_full_name is not None:
            repo = self.get_by_full_name(repository_full_name)
        if repo is None:
            return False
        return repo.data.installed

    def get_by_id(self, repository_id: str | None) -> Repository | None:
        """Get repository by id."""
        if not repository_id:
            return None
        return self._repositories_by_id.get(str(repository_id))

    def get_by_full_name(self, repository_full_name: str | None) -> Repository | None:
        """Get repository by full name."""
        if not repository_full_name:
            return None
        return self._repositories_by_full_name.get(repository_full_name.lower())

    def is_removed(self, repository_full_name: str) -> bool:
        """Check if a repository is removed."""
        return repository_full_name in self._removed_repositories_by_full_name

    def removed_repository(self, repository_full_name: str) -> RemovedRepository:
        """Get repository by full name."""
        if removed := self._removed_repositories_by_full_name.get(repository_full_name):
            return removed

        removed = RemovedRepository(repository=repository_full_name)
        self._removed_repositories_by_full_name[repository_full_name] = removed
        return removed


class MarketplaceManager:
    """The Marketplace, its state and everything it manages."""

    data: MarketplaceData
    data_client: CatalogClient
    githubapi: GitHubAPI
    hass: HomeAssistant
    queue: QueueManager
    session: ClientSession
    stage: MarketplaceStage | None = None
    version: AwesomeVersion

    def __init__(self) -> None:
        """Initialize."""
        self.common = MarketplaceCommon()
        self.configuration = MarketplaceConfiguration()
        self.coordinators: dict[str, MarketplaceUpdateCoordinator] = {}
        self.core = MarketplaceCore()
        self.recurring_tasks: list[Callable[[], None]] = []
        self.repositories = Repositories()
        self.status = MarketplaceStatus()
        self.system = MarketplaceSystem()

    def set_stage(self, stage: MarketplaceStage | None) -> None:
        """Set the stage the Marketplace is in."""
        if stage and self.stage == stage:
            return

        self.stage = stage
        if stage is not None:
            LOGGER.info("Stage changed: %s", self.stage)
            self.async_dispatch(MarketplaceSignal.STAGE, {"stage": self.stage})

    def disable(self, reason: DisabledReason) -> None:
        """Disable the Marketplace."""
        if self.system.disabled_reason == reason:
            return

        self.system.disabled_reason = reason
        if reason != DisabledReason.REMOVED:
            LOGGER.error("The Marketplace is disabled - %s", reason)

        if (
            reason == DisabledReason.INVALID_TOKEN
            and (config_entry := self.configuration.config_entry) is not None
        ):
            self.hass.add_job(config_entry.async_start_reauth, self.hass)

    def enable(self) -> None:
        """Enable the Marketplace."""
        if self.system.disabled_reason is not None:
            self.system.disabled_reason = None
            LOGGER.info("The Marketplace is enabled")

    def enable_category(self, category: RepositoryCategory) -> None:
        """Enable a repository category."""
        if category not in self.common.categories:
            LOGGER.info("Enable category: %s", category)
            self.common.categories.add(category)
            self.coordinators[category] = MarketplaceUpdateCoordinator()

    async def async_save_file(self, file_path: str, content: Any) -> bool:
        """Save a file."""

        def _write_file():
            with open(
                file_path,
                mode="w" if isinstance(content, str) else "wb",
                encoding="utf-8" if isinstance(content, str) else None,
                errors="ignore" if isinstance(content, str) else None,
            ) as file_handler:
                file_handler.write(content)

            # Create gz for .js files
            if os.path.isfile(file_path):
                if file_path.endswith(".js"):
                    with (
                        open(file_path, "rb") as f_in,
                        gzip.open(file_path + ".gz", "wb") as f_out,
                    ):
                        shutil.copyfileobj(f_in, f_out)

            # LEGACY! Remove with 2.0
            if "themes" in file_path and file_path.endswith(".yaml"):
                filename = file_path.rsplit("/", maxsplit=1)[-1]
                base = file_path.split("/themes/", maxsplit=1)[0]
                combined = f"{base}/themes/{filename}"
                if os.path.exists(combined):
                    LOGGER.info("Removing old theme file %s", combined)
                    os.remove(combined)

        try:
            await self.hass.async_add_executor_job(_write_file)
        except OSError as error:
            LOGGER.error("Could not write data to %s - %s", file_path, error)
            return False

        return await async_exists(self.hass, file_path)

    async def async_can_update(self) -> int:
        """Helper to calculate the number of repositories we can fetch data for."""
        try:
            response = await self.async_github_api_method(self.githubapi.rate_limit)
            if ((limit := response.data.resources.core.remaining or 0) - 1000) >= 10:
                return math.floor((limit - 1000) / 10)
            reset = dt_util.as_local(
                dt_util.utc_from_timestamp(response.data.resources.core.reset)
            )
            LOGGER.info(
                "GitHub API ratelimited - %s remaining (%s)",
                response.data.resources.core.remaining,
                f"{reset.hour}:{reset.minute}:{reset.second}",
            )
            self.disable(DisabledReason.RATE_LIMIT)
        except MarketplaceError:
            LOGGER.exception("Could not get the GitHub API rate limit")

        return 0

    @overload
    async def async_github_api_method(
        self,
        method: Callable[..., Awaitable[TV]],
        *args: Any,
        raise_exception: Literal[True] = True,
        **kwargs: Any,
    ) -> TV: ...

    @overload
    async def async_github_api_method(
        self,
        method: Callable[..., Awaitable[TV]],
        *args: Any,
        raise_exception: bool,
        **kwargs: Any,
    ) -> TV | None: ...

    async def async_github_api_method(
        self,
        method: Callable[..., Awaitable[TV]],
        *args: Any,
        raise_exception: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Call a GitHub API method."""
        _exception = None

        try:
            return await method(*args, **kwargs)
        except GitHubAuthenticationException as exception:
            self.disable(DisabledReason.INVALID_TOKEN)
            _exception = exception
        except GitHubRatelimitException as exception:
            self.disable(DisabledReason.RATE_LIMIT)
            _exception = exception
        except GitHubNotModifiedException:
            raise
        except GitHubException as exception:
            _exception = exception
        except Exception as exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error calling the GitHub API")
            _exception = exception

        if raise_exception and _exception is not None:
            raise MarketplaceError(_exception)
        return None

    async def async_register_repository(
        self,
        repository_full_name: str,
        category: RepositoryCategory,
        *,
        check: bool = True,
        ref: str | None = None,
        repository_id: str | None = None,
        default: bool = False,
    ) -> list[str] | None:
        """Register a repository."""
        if repository_full_name in self.common.skip:
            raise ExpectedError(f"Skipping {repository_full_name}")

        if repository_full_name == "home-assistant/core":
            raise CoreRepositoryError

        if (
            repository_full_name == "home-assistant/addons"
            or repository_full_name.startswith("hassio-addons/")
        ):
            raise AppRepositoryError

        if category not in REPOSITORY_CLASSES:
            LOGGER.warning(
                "%s is not a valid repository category, %s will not be registered",
                category,
                repository_full_name,
            )
            return None

        if (
            renamed := self.common.renamed_repositories.get(repository_full_name)
        ) is not None:
            repository_full_name = renamed

        repository: Repository = REPOSITORY_CLASSES[category](
            self, repository_full_name
        )
        if check:
            try:
                await repository.async_registration(ref)
                if repository.validate.errors:
                    self.common.skip.add(repository.data.full_name)
                    if not self.status.startup:
                        LOGGER.error("Validation for %s failed", repository_full_name)
                    return repository.validate.errors
                repository.logger.info("%s Registration completed", repository.string)
            except RepositoryExistsError, RepositoryArchivedError:
                return None
            except GitHubException as exception:
                self.common.skip.add(repository.data.full_name)
                raise MarketplaceError(
                    f"Validation for {repository_full_name} failed with {exception}."
                ) from exception

        if self.status.new:
            repository.data.new = False

        if repository_id is not None:
            repository.data.id = repository_id

        elif self.hass is not None and check and repository.data.new:
            self.async_dispatch(
                MarketplaceSignal.REPOSITORY,
                {
                    "action": "registration",
                    "repository": repository.data.full_name,
                    "repository_id": repository.data.id,
                },
            )

        self.repositories.register(repository, default)
        return None

    async def startup_tasks(self, _: HomeAssistant | None = None) -> None:
        """Tasks that are started after setup."""
        self.set_stage(MarketplaceStage.STARTUP)

        if critical := await async_load_from_storage(self.hass, "critical"):
            for repo in critical:
                if not repo["acknowledged"]:
                    LOGGER.critical("URGENT!: Check the Marketplace!")
                    async_create_persistent_notification(
                        self.hass,
                        title="URGENT!",
                        message="**Check the Marketplace!**",
                    )
                    break

        self.recurring_tasks.append(
            async_track_time_interval(
                self.hass,
                self.async_update_downloaded_custom_repositories,
                timedelta(hours=48),
            )
        )

        self.recurring_tasks.append(
            async_track_time_interval(
                self.hass, self.async_get_all_category_repositories, timedelta(hours=6)
            )
        )

        self.recurring_tasks.append(
            async_track_time_interval(
                self.hass, self.async_check_rate_limit, timedelta(minutes=5)
            )
        )
        self.recurring_tasks.append(
            async_track_time_interval(
                self.hass, self.async_process_queue, timedelta(minutes=10)
            )
        )

        self.recurring_tasks.append(
            async_track_time_interval(
                self.hass, self.async_handle_critical_repositories, timedelta(hours=6)
            )
        )

        unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_FINAL_WRITE, self.data.async_force_write
        )
        if config_entry := self.configuration.config_entry:
            config_entry.async_on_unload(unsub)

        LOGGER.debug(
            "There are %s scheduled recurring tasks", len(self.recurring_tasks)
        )

        self.status.startup = False
        self.async_dispatch(MarketplaceSignal.STATUS, {})

        await self.async_handle_removed_repositories()
        await self.async_get_all_category_repositories()

        self.set_stage(MarketplaceStage.RUNNING)

        self.async_dispatch(MarketplaceSignal.RELOAD, {"force": True})

        await self.async_handle_critical_repositories()
        await self.async_process_queue()

        self.async_dispatch(MarketplaceSignal.STATUS, {})

    async def async_download_file(
        self,
        url: str,
        *,
        headers: dict | None = None,
        keep_url: bool = False,
        nolog: bool = False,
        handle_rate_limit: bool = False,
        **_,
    ) -> bytes | None:
        """Download files, and return the content."""
        if url is None:
            return None

        if not keep_url and "tags/" in url:
            url = url.replace("tags/", "")

        LOGGER.debug("Trying to download %s", url)
        attempt_count = 0

        while attempt_count < 5:
            try:
                request = await self.session.get(
                    url=url,
                    timeout=ClientTimeout(total=60),
                    headers=headers,
                )

                # Make sure that we got a valid result
                if request.status == 200:
                    if _declared_size(request.headers) > MAX_DOWNLOAD_SIZE:
                        raise MarketplaceError(  # noqa: TRY301 # handled below
                            f"{url} declares more than the "
                            f"{MAX_DOWNLOAD_SIZE} byte limit"
                        )

                    content = await request.read()
                    if len(content) > MAX_DOWNLOAD_SIZE:
                        raise MarketplaceError(  # noqa: TRY301 # handled below
                            f"{url} is larger than the {MAX_DOWNLOAD_SIZE} byte limit"
                        )

                    return content

                # Handle rate-limits
                if handle_rate_limit and request.status == 429:
                    try:
                        header = int(request.headers.get("retry-after") or 10)
                    except ValueError, TypeError:
                        header = 10
                    retry_after = min(header, 60)  # Limit to 60 seconds

                    LOGGER.warning(
                        "GitHub has imposed a ratelimit on the request for %s, "
                        "retrying after %s seconds",
                        url,
                        retry_after,
                    )
                    attempt_count += 1
                    await asyncio.sleep(retry_after)
                    continue

                raise MarketplaceError(  # noqa: TRY301 # handled by the retry loop below
                    f"Got status code {request.status} when trying to download {url}"
                )
            except TimeoutError:
                LOGGER.warning(
                    "A timeout of 60! seconds was encountered while downloading %s, "
                    "using over 60 seconds to download a single file is not normal. "
                    "This is not a problem with the Marketplace but how your host communicates with GitHub. "
                    "Retrying up to 5 times to mask/hide your host/network problems to "
                    "stop the flow of issues opened about it. "
                    "Tries left %s",
                    url,
                    (4 - attempt_count),
                )
                attempt_count += 1
                await asyncio.sleep(1)
                continue

            except Exception:  # noqa: BLE001
                if not nolog:
                    LOGGER.exception("Download of %s failed", url)

            return None
        return None

    async def async_recreate_entities(self) -> None:
        """Recreate entities."""
        if (config_entry := self.configuration.config_entry) is None:
            return

        platforms = [Platform.UPDATE]

        await self.hass.config_entries.async_unload_platforms(
            entry=config_entry,
            platforms=platforms,
        )
        await self.hass.config_entries.async_forward_entry_setups(
            config_entry, platforms
        )

    @callback
    def async_dispatch(
        self, signal: MarketplaceSignal, data: dict[str, Any] | None = None
    ) -> None:
        """Dispatch a signal with data."""
        async_dispatcher_send(self.hass, signal, data)

    def set_active_categories(self) -> None:
        """Set the active categories."""
        self.common.categories = set()
        for category in (
            RepositoryCategory.INTEGRATION,
            RepositoryCategory.PLUGIN,
            RepositoryCategory.TEMPLATE,
        ):
            self.enable_category(RepositoryCategory(category))

        if (
            RepositoryCategory.PYTHON_SCRIPT in self.hass.config.components
            or self.repositories.category_downloaded(RepositoryCategory.PYTHON_SCRIPT)
        ):
            self.enable_category(RepositoryCategory.PYTHON_SCRIPT)

        if self.hass.services.has_service(
            "frontend", "reload_themes"
        ) or self.repositories.category_downloaded(RepositoryCategory.THEME):
            self.enable_category(RepositoryCategory.THEME)

        if self.configuration.appdaemon:
            self.enable_category(RepositoryCategory.APPDAEMON)

    async def async_get_all_category_repositories(
        self, _: datetime | None = None
    ) -> None:
        """Get all category repositories."""
        if self.system.disabled:
            return
        LOGGER.info("Loading known repositories")
        await asyncio.gather(
            *[
                self.async_get_category_repositories_experimental(category)
                for category in self.common.categories or []
            ]
        )

    async def async_get_category_repositories_experimental(
        self, category: RepositoryCategory
    ) -> None:
        """Update all category repositories."""
        LOGGER.debug("Fetching updated content for %s", category)
        try:
            category_data = await self.data_client.get_data(category, validate=True)
        except NotModifiedError:
            LOGGER.debug("No updates for %s", category)
            return
        except MarketplaceError as exception:
            LOGGER.error("Could not update %s - %s", category, exception)
            return

        # The Marketplace is part of Home Assistant, it does not manage itself
        category_data = {
            repo_id: repo_data
            for repo_id, repo_data in category_data.items()
            if repo_data["full_name"] != LEGACY_HACS_INTEGRATION_REPOSITORY
        }

        await self.data.register_unknown_repositories(category_data, category)

        for repo_id, repo_data in category_data.items():
            repo_name = repo_data["full_name"]
            if self.common.renamed_repositories.get(repo_name):
                repo_name = self.common.renamed_repositories[repo_name]
            if self.repositories.is_removed(repo_name):
                continue
            if repo_name in self.common.archived_repositories:
                continue
            if repository := self.repositories.get_by_full_name(repo_name):
                self.repositories.set_repository_id(repository, repo_id)
                self.repositories.mark_default(repository)
                if repository.data.last_fetched is None or (
                    repository.data.last_fetched.timestamp() < repo_data["last_fetched"]
                ):
                    repository.data.update_data(
                        {**dict(REPOSITORY_KEYS_TO_EXPORT), **repo_data}
                    )
                    if (manifest := repo_data.get("manifest")) is not None:
                        repository.repository_manifest.update_data(
                            {**dict(REPOSITORY_MANIFEST_KEYS_TO_EXPORT), **manifest}
                        )

        if self.stage == MarketplaceStage.STARTUP:
            for repository in self.repositories.list_all:
                if (
                    repository.data.category == category
                    and not repository.data.installed
                    and not self.repositories.is_default(str(repository.data.id))
                ):
                    repository.logger.debug(
                        "%s Unregister stale custom repository", repository.string
                    )
                    self.repositories.unregister(repository)

        self.async_dispatch(MarketplaceSignal.REPOSITORY, {})
        self.coordinators[category].async_update_listeners()

    async def async_check_rate_limit(self, _: datetime | None = None) -> None:
        """Check rate limit."""
        if (
            not self.system.disabled
            or self.system.disabled_reason != DisabledReason.RATE_LIMIT
        ):
            return

        LOGGER.debug("Checking if ratelimit has lifted")
        can_update = await self.async_can_update()
        LOGGER.debug("Ratelimit indicate we can update %s", can_update)
        if can_update > 0:
            self.enable()
            await self.async_process_queue()

    async def async_process_queue(self, _: datetime | None = None) -> None:
        """Process the queue."""
        if self.system.disabled:
            LOGGER.debug("The Marketplace is disabled")
            return
        if not self.queue.has_pending_tasks:
            LOGGER.debug("Nothing in the queue")
            return
        if self.queue.running:
            LOGGER.debug("Queue is already running")
            return

        async def _handle_queue() -> None:
            if not self.queue.has_pending_tasks:
                await self.data.async_write()
                return
            can_update = await self.async_can_update()
            LOGGER.debug(
                "Can update %s repositories, items in queue %s",
                can_update,
                self.queue.pending_tasks,
            )
            if can_update != 0:
                try:
                    await self.queue.execute(can_update)
                except ExecutionInProgressError:
                    return

                await _handle_queue()

        await _handle_queue()

    async def async_handle_removed_repositories(
        self, _: datetime | None = None
    ) -> None:
        """Handle removed repositories."""
        if self.system.disabled:
            return
        need_to_save = False
        LOGGER.info("Loading removed repositories")

        try:
            removed_repositories = await self.data_client.get_data(
                "removed", validate=True
            )
        except MarketplaceError:
            return

        for item in removed_repositories:
            removed = self.repositories.removed_repository(item["repository"])
            removed.update_data(item)

        for removed in self.repositories.list_removed:
            if (
                repository := self.repositories.get_by_full_name(removed.repository)
            ) is None:
                continue
            if repository.data.full_name in self.common.ignored_repositories:
                continue
            if repository.data.installed:
                if removed.removal_type != "critical":
                    async_create_issue(
                        hass=self.hass,
                        domain=DOMAIN,
                        issue_id=f"removed_{repository.data.id}",
                        is_fixable=False,
                        issue_domain=DOMAIN,
                        severity=IssueSeverity.WARNING,
                        translation_key="removed",
                        translation_placeholders={
                            "name": repository.data.full_name,
                            "reason": str(removed.reason),
                            "repositry_id": str(repository.data.id),
                        },
                    )
                    LOGGER.warning(
                        "You have '%s' downloaded with the Marketplace, "
                        "this repository has been removed, please consider removing it. "
                        "Removal reason (%s)",
                        repository.data.full_name,
                        removed.reason,
                    )
            else:
                need_to_save = True
                repository.remove()

        if need_to_save:
            await self.data.async_write()

    async def async_update_downloaded_custom_repositories(
        self, _: datetime | None = None
    ) -> None:
        """Execute the task."""
        if self.system.disabled:
            return
        LOGGER.info(
            "Starting recurring background task for downloaded custom repositories"
        )

        repositories_to_update = 0
        repositories_updated = asyncio.Event()

        async def update_repository(repository: Repository) -> None:
            """Update a repository."""
            nonlocal repositories_to_update
            await repository.update_repository(ignore_issues=True)
            repositories_to_update -= 1
            if not repositories_to_update:
                repositories_updated.set()

        for repository in self.repositories.list_downloaded:
            if (
                repository.data.category in self.common.categories
                and not self.repositories.is_default(str(repository.data.id))
            ):
                repositories_to_update += 1
                self.queue.add(update_repository(repository))

        async def update_coordinators() -> None:
            """Update all coordinators."""
            await repositories_updated.wait()
            for coordinator in self.coordinators.values():
                coordinator.async_update_listeners()

        if config_entry := self.configuration.config_entry:
            config_entry.async_create_background_task(
                self.hass, update_coordinators(), "update_coordinators"
            )
        else:
            self.hass.async_create_background_task(
                update_coordinators(), "update_coordinators"
            )

        LOGGER.debug(
            "Recurring background task for downloaded custom repositories done"
        )

    async def async_handle_critical_repositories(
        self, _: datetime | None = None
    ) -> None:
        """Handle critical repositories."""
        critical_queue = QueueManager(hass=self.hass)
        instored: list[str] = []
        critical: list[dict[str, Any]] = []
        was_installed = False

        try:
            critical = await self.data_client.get_data("critical", validate=True)
        except GitHubNotModifiedException, NotModifiedError:
            return
        except MarketplaceError:
            pass

        if not critical:
            LOGGER.debug("No critical repositories")
            return

        stored_critical = await async_load_from_storage(self.hass, "critical")

        instored.extend(stored["repository"] for stored in stored_critical or [])

        stored_critical = []

        for repository in critical:
            removed_repo = self.repositories.removed_repository(
                repository["repository"]
            )
            removed_repo.removal_type = "critical"
            repo = self.repositories.get_by_full_name(repository["repository"])

            stored = {
                "repository": repository["repository"],
                "reason": repository["reason"],
                "link": repository["link"],
                "acknowledged": True,
            }
            if repository["repository"] not in instored:
                if repo is not None and repo.data.installed:
                    LOGGER.critical(
                        "Removing repository %s, it is marked as critical",
                        repository["repository"],
                    )
                    was_installed = True
                    stored["acknowledged"] = False
                    # Remove from the Marketplace
                    critical_queue.add(repo.uninstall())
                    repo.remove()

            stored_critical.append(stored)
            removed_repo.update_data(stored)

        # Uninstall
        await critical_queue.execute()

        # Save to FS
        await async_save_to_storage(self.hass, "critical", stored_critical)

        # Restart HASS
        if was_installed:
            LOGGER.critical("Restarting Home Assistant")
            self.hass.async_create_task(self.hass.async_stop(100))


type MarketplaceConfigEntry = ConfigEntry[MarketplaceManager]


@callback
def async_get_marketplace(hass: HomeAssistant) -> MarketplaceManager:
    """Return the Marketplace of the loaded config entry.

    For the code that has no config entry at hand, like the WebSocket API and
    the system health info. The manifest sets single_config_entry, so there is
    never more than one entry to pick from.
    """
    if not (entries := hass.config_entries.async_loaded_entries(DOMAIN)):
        raise HomeAssistantError("The Marketplace is not loaded")

    entry: MarketplaceConfigEntry = entries[0]
    return entry.runtime_data
