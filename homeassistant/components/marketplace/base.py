"""Base classes for the Marketplace."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import gzip
import math
import os
import shutil
import tempfile
from typing import TYPE_CHECKING, Any, Literal, Self, overload

from aiogithubapi import (
    GitHubAPI,
    GitHubAuthenticationException,
    GitHubException,
    GitHubNotModifiedException,
    GitHubRatelimitException,
)
from aiohttp.client import ClientSession, ClientTimeout
from awesomeversion import AwesomeVersion

from homeassistant.components.lovelace import LOVELACE_DATA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    Platform,
    __version__ as HAVERSION,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.util import dt as dt_util

from .const import (
    CLIENT_NAME,
    CONF_WARNING_ACCEPTED,
    DOMAIN,
    LEGACY_HACS_INTEGRATION_REPOSITORY,
    RESTART_ISSUE_PREFIX,
    TV,
    WARNING_REMINDER_INTERVAL,
    WARNING_VERSION,
)
from .coordinator import MarketplaceUpdateCoordinator
from .critical import async_create_critical_repository_issue
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
    GitHubAnonymousRateLimitError,
    GitHubRateLimitError,
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
from .utils.data import MarketplaceData
from .utils.file_system import async_exists
from .utils.identity import newest_id_per_name
from .utils.logger import LOGGER
from .utils.queue_manager import QueueManager
from .utils.response import async_read_limited
from .utils.storage import async_load_from_storage, async_save_to_storage

if TYPE_CHECKING:
    from .repositories.base import Repository


# A release can be large, only a stalled connection counts as a failure
DOWNLOAD_TIMEOUT = ClientTimeout(total=10 * 60, sock_read=60)


@dataclass
class RemovedRepository:
    """Removed repository."""

    repository: str | None = None
    reason: str | None = None
    link: str | None = None
    removal_type: str | None = None
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
    """Configuration of the Marketplace, read from its config entry."""

    config_entry: MarketplaceConfigEntry
    token: str | None = None
    debug: bool = False
    plugin_path: str = "www/community/"
    theme_path: str = "themes/"

    @classmethod
    def from_entry(cls, config_entry: MarketplaceConfigEntry) -> Self:
        """Read the configuration from a config entry.

        Entries the custom integration created can carry keys that mean
        nothing here, the paths the Marketplace writes to are not settable.
        """
        return cls(config_entry=config_entry, token=config_entry.data.get(CONF_TOKEN))


@dataclass
class MarketplaceCore:
    """Core info the Marketplace needs."""

    config_path: str
    lovelace_mode: LovelaceMode


@dataclass
class MarketplaceCommon:
    """Common data of the Marketplace."""

    categories: set[RepositoryCategory] = field(default_factory=set)
    renamed_repositories: dict[str, str] = field(default_factory=dict)
    archived_repositories: set[str] = field(default_factory=set)
    ignored_repositories: set[str] = field(default_factory=set)
    # The ids of repositories added by hand, the catalog does not list them
    custom_repositories: set[str] = field(default_factory=set)
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

    @property
    def removed(self) -> bool:
        """Return if the Marketplace is being removed.

        The catalog is no GitHub API call, only this stops the work on it.
        """
        return self.disabled_reason is DisabledReason.REMOVED


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
    def list_installed(self) -> list[Repository]:
        """Return a list of installed repositories."""
        return [repo for repo in self._repositories if repo.data.installed]

    def category_installed(self, category: RepositoryCategory) -> bool:
        """Check if a given category has been installed."""
        for repository in self.list_installed:
            if repository.data.category == category:
                return True
        return False

    def register(self, repository: Repository, default: bool = False) -> None:
        """Register a repository."""
        repo_id = repository.data.id

        if repo_id == "0":
            return

        if registered_repo := self._repositories_by_id.get(repo_id):
            if registered_repo.data.full_name == repository.data.full_name:
                return

            # Renamed on GitHub, the registered one keeps what it had
            self.rename(registered_repo, repository.data.full_name)
            registered_repo.data.new = False
            repository = registered_repo

        if repository not in self._repositories:
            self._repositories.add(repository)

        self._repositories_by_id[repo_id] = repository
        self._repositories_by_full_name[repository.data.full_name_lower] = repository

        if default:
            self.mark_default(repository)

    def rename(self, repository: Repository, full_name: str) -> None:
        """Rename a repository, it is looked up by its new name from now on."""
        if self._repositories_by_full_name.get(repository.data.full_name_lower) is (
            repository
        ):
            self._repositories_by_full_name.pop(repository.data.full_name_lower)

        repository.data.full_name = full_name

        if repository in self._repositories:
            self._repositories_by_full_name[repository.data.full_name_lower] = (
                repository
            )

    def unregister(self, repository: Repository) -> None:
        """Unregister a repository."""
        repo_id = repository.data.id

        if repo_id == "0":
            return

        if not self.is_registered(repository_id=repo_id):
            return

        if self.is_default(repo_id):
            self._default_repositories.remove(repo_id)

        if repository in self._repositories:
            self._repositories.remove(repository)

        # Another repository can hold the name or the id by now, it keeps them
        if self._repositories_by_id.get(repo_id) is repository:
            self._repositories_by_id.pop(repo_id)
        if self._repositories_by_full_name.get(repository.data.full_name_lower) is (
            repository
        ):
            self._repositories_by_full_name.pop(repository.data.full_name_lower)

    def mark_default(self, repository: Repository) -> None:
        """Mark a repository as default."""
        repo_id = repository.data.id

        if repo_id == "0":
            return

        if not self.is_registered(repository_id=repo_id):
            return

        self._default_repositories.add(repo_id)

    def set_repository_id(self, repository: Repository, repo_id: str) -> None:
        """Update a repository id."""
        existing_repo_id = repository.data.id
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

    def is_installed(self, repository_id: str) -> bool:
        """Return if a repository is installed."""
        repository = self.get_by_id(repository_id)
        return repository is not None and repository.data.installed

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
        """Return the removed entry of a repository, created when there is none."""
        if removed := self._removed_repositories_by_full_name.get(repository_full_name):
            return removed

        removed = RemovedRepository(repository=repository_full_name)
        self._removed_repositories_by_full_name[repository_full_name] = removed
        return removed


class MarketplaceManager:
    """The Marketplace, its state and everything it manages."""

    def __init__(
        self, hass: HomeAssistant, config_entry: MarketplaceConfigEntry
    ) -> None:
        """Set up the Marketplace of a config entry, nothing runs yet."""
        self.hass = hass
        self.configuration = MarketplaceConfiguration.from_entry(config_entry)
        self.core = MarketplaceCore(
            config_path=hass.config.path(),
            lovelace_mode=LovelaceMode(hass.data[LOVELACE_DATA].resource_mode),
        )
        self.version = AwesomeVersion(HAVERSION)

        self.session: ClientSession = async_get_clientsession(hass)
        # An empty token keeps aiogithubapi from reading GITHUB_TOKEN from the
        # environment, without a connected account the calls are anonymous.
        self.githubapi = GitHubAPI(
            token=self.configuration.token or "",
            session=self.session,
            client_name=CLIENT_NAME,
        )
        self.data_client = CatalogClient(session=self.session, client_name=CLIENT_NAME)

        self.data = MarketplaceData(marketplace=self)
        self.queue = QueueManager(hass=hass)
        self.stage: MarketplaceStage | None = None
        self.common = MarketplaceCommon()
        self.critical_repositories: list[dict[str, Any]] = []
        self.coordinators: dict[str, MarketplaceUpdateCoordinator] = {}
        self.recurring_tasks: list[Callable[[], None]] = []
        self.recurring_runs: set[asyncio.Task[None]] = set()
        self.startup_task: asyncio.Task[None] | None = None
        self.repositories = Repositories()
        self.status = MarketplaceStatus()
        self.system = MarketplaceSystem()

    def _async_track_interval(
        self,
        action: Callable[[datetime], Coroutine[Any, Any, None]],
        interval: timedelta,
    ) -> None:
        """Run an action on an interval, as a task an unload can stop."""

        @callback
        def _async_run(now: datetime) -> None:
            run = self.hass.async_create_background_task(
                action(now), f"marketplace {action.__name__}"
            )
            self.recurring_runs.add(run)
            run.add_done_callback(self.recurring_runs.discard)

        self.recurring_tasks.append(
            async_track_time_interval(self.hass, _async_run, interval)
        )

    @property
    def github_connected(self) -> bool:
        """Return if a GitHub account is connected."""
        return bool(self.configuration.token)

    @property
    def warning_acceptances(self) -> dict[str, datetime]:
        """Return when each user accepted the current version of the warning."""
        config_entry = self.configuration.config_entry
        return {
            user_id: accepted_at
            for user_id, acceptance in config_entry.data.get(
                CONF_WARNING_ACCEPTED, {}
            ).items()
            if acceptance["version"] >= WARNING_VERSION
            # A date that can not be read is no acceptance
            and (accepted_at := dt_util.parse_datetime(acceptance["accepted_at"]))
        }

    def warning_accepted(self, user_id: str) -> bool:
        """Return if a user accepted the current version of the first-run warning."""
        return user_id in self.warning_acceptances

    def warning_reminder_due(self, user_id: str) -> bool:
        """Return if the warning a user accepted is due to be shown again."""
        if (accepted_at := self.warning_acceptances.get(user_id)) is None:
            return False

        return dt_util.utcnow() - accepted_at > WARNING_REMINDER_INTERVAL

    @callback
    def async_forget_warning_acceptance(self, user_id: str) -> None:
        """Forget the acceptance of a user who was removed."""
        config_entry = self.configuration.config_entry
        acceptances = config_entry.data.get(CONF_WARNING_ACCEPTED, {})
        if user_id not in acceptances:
            return

        self.hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                CONF_WARNING_ACCEPTED: {
                    accepted_by: acceptance
                    for accepted_by, acceptance in acceptances.items()
                    if accepted_by != user_id
                },
            },
        )

    @callback
    def async_accept_warning(self, user_id: str) -> None:
        """Store that a user accepted the current version of the first-run warning."""
        config_entry = self.configuration.config_entry
        self.hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                CONF_WARNING_ACCEPTED: {
                    **config_entry.data.get(CONF_WARNING_ACCEPTED, {}),
                    user_id: {
                        "version": WARNING_VERSION,
                        "accepted_at": dt_util.utcnow().isoformat(),
                    },
                },
            },
        )
        self.async_dispatch(MarketplaceSignal.CONFIG, {})

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
        # The panel shows the reason, it comes and goes without a write
        self.async_dispatch(MarketplaceSignal.CONFIG, {})

        if reason == DisabledReason.INVALID_TOKEN:
            self.configuration.config_entry.async_start_reauth(self.hass)

    def enable(self) -> None:
        """Enable the Marketplace."""
        if self.system.disabled_reason is not None:
            self.system.disabled_reason = None
            LOGGER.info("The Marketplace is enabled")
            self.async_dispatch(MarketplaceSignal.CONFIG, {})

    def enable_category(self, category: RepositoryCategory) -> None:
        """Enable a repository category."""
        if category not in self.common.categories:
            LOGGER.info("Enable category: %s", category)
            self.common.categories.add(category)
            self.coordinators[category] = MarketplaceUpdateCoordinator()

    async def async_save_file(self, file_path: str, content: Any) -> bool:
        """Save a file."""

        def _write_file() -> None:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(
                file_path,
                mode="w" if isinstance(content, str) else "wb",
                encoding="utf-8" if isinstance(content, str) else None,
                errors="ignore" if isinstance(content, str) else None,
            ) as file_handler:
                file_handler.write(content)

            if os.path.isfile(file_path) and file_path.endswith(".js"):
                # Swapped in whole, a release can ship this same .gz file
                # and write it while this one is being compressed
                handle, compressed = tempfile.mkstemp(
                    dir=os.path.dirname(file_path), suffix=".gz.tmp"
                )
                os.close(handle)
                try:
                    with (
                        open(file_path, "rb") as f_in,
                        gzip.open(compressed, "wb") as f_out,
                    ):
                        shutil.copyfileobj(f_in, f_out)
                    os.replace(compressed, f"{file_path}.gz")
                finally:
                    if os.path.exists(compressed):
                        os.remove(compressed)

        try:
            await self.hass.async_add_executor_job(_write_file)
        except OSError as error:
            LOGGER.error("Could not write data to %s - %s", file_path, error)
            return False

        return await async_exists(self.hass, file_path)

    async def async_can_update(self) -> int:
        """Return how many repositories the rate limit leaves room for."""
        # The anonymous rate limit is too small to spend on background work
        if not self.github_connected:
            return 0

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
        """Call a GitHub API method.

        Without a connected account the call is anonymous, a refusal then only
        fails the call that hit it. An anonymous rate limit always raises, so
        the action that hit it fails instead of carrying on with stale data.
        """
        _exception = None

        try:
            return await method(*args, **kwargs)
        except GitHubAuthenticationException as exception:
            if self.github_connected:
                self.disable(DisabledReason.INVALID_TOKEN)
            _exception = exception
        except GitHubRatelimitException as exception:
            if not self.github_connected:
                raise GitHubAnonymousRateLimitError(exception) from exception
            self.disable(DisabledReason.RATE_LIMIT)
            if raise_exception:
                raise GitHubRateLimitError(exception) from exception
            return None
        except GitHubNotModifiedException:
            raise
        except GitHubException as exception:
            _exception = exception
        except Exception as exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error calling the GitHub API")
            _exception = exception

        if raise_exception and _exception is not None:
            raise MarketplaceError(_exception) from _exception
        return None

    @callback
    def async_set_repository_id(self, repository: Repository, repo_id: str) -> None:
        """Give a repository the id it is known by now.

        GitHub gives a repository that was deleted and created again a new id,
        its name is what stays. What was installed, its entities and its device
        move along to the new id.
        """
        previous_id = repository.data.id
        if previous_id in ("0", repo_id):
            self.repositories.set_repository_id(repository, repo_id)
            return

        was_default = self.repositories.is_default(previous_id)
        self.repositories.unregister(repository)
        repository.data.id = repo_id
        self.repositories.register(repository, default=was_default)

        if previous_id in self.common.custom_repositories:
            self.common.custom_repositories.discard(previous_id)
            self.common.custom_repositories.add(repo_id)

        self._async_move_restart_issues(previous_id, repo_id)
        self._async_move_entities(previous_id, repo_id)
        self._async_move_device(previous_id, repo_id)

        LOGGER.info(
            "%s moved from id %s to %s, it was created again on GitHub",
            repository.data.full_name,
            previous_id,
            repo_id,
        )

    def _async_move_restart_issues(self, previous_id: str, repo_id: str) -> None:
        """Move the restart repairs of a repository to its new id."""
        # The repair is how a reload knows the install still waits for a restart
        previous_prefix = f"{RESTART_ISSUE_PREFIX}{previous_id}_"
        issue_registry = ir.async_get(self.hass)
        for domain, issue_id in list(issue_registry.issues):
            if domain != DOMAIN or not issue_id.startswith(previous_prefix):
                continue

            issue = issue_registry.issues[(domain, issue_id)]
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id.replace(
                    previous_prefix, f"{RESTART_ISSUE_PREFIX}{repo_id}_", 1
                ),
                is_fixable=True,
                issue_domain=issue.issue_domain,
                severity=IssueSeverity.WARNING,
                translation_key="restart_required",
                translation_placeholders=issue.translation_placeholders,
            )
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def _async_move_entities(self, previous_id: str, repo_id: str) -> None:
        """Move the entities of a repository to its new id."""
        entity_registry = er.async_get(self.hass)
        for platform in (Platform.SWITCH, Platform.UPDATE):
            entity_id = entity_registry.async_get_entity_id(
                platform, DOMAIN, previous_id
            )
            if entity_id is None:
                continue

            if entity_registry.async_get_entity_id(platform, DOMAIN, repo_id):
                entity_registry.async_remove(entity_id)
            else:
                entity_registry.async_update_entity(entity_id, new_unique_id=repo_id)

    def _async_move_device(self, previous_id: str, repo_id: str) -> None:
        """Move the device of a repository to its new id."""
        entry_id = self.configuration.config_entry.entry_id
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, previous_id), entry_id
        )
        if device is None:
            return

        if device_registry.async_get_device_by_identifier((DOMAIN, repo_id), entry_id):
            device_registry.async_remove_device(device.id)
        else:
            device_registry.async_update_device(
                device.id, new_identifiers={(DOMAIN, repo_id)}
            )

    async def async_register_repository(
        self,
        repository_full_name: str,
        category: RepositoryCategory,
        *,
        check: bool = True,
        repository_id: str | None = None,
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
                await repository.async_registration()
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

        elif check and repository.data.new:
            repository.async_dispatch_changed("registration")

        self.repositories.register(repository)
        if check:
            self.common.custom_repositories.add(repository.data.id)
        return None

    async def startup_tasks(self, _: HomeAssistant | None = None) -> None:
        """Tasks that are started after setup."""
        self.set_stage(MarketplaceStage.STARTUP)

        # Removals nobody confirmed yet, also those made before the takeover
        for critical in await async_load_from_storage(self.hass, "critical") or []:
            if not critical["acknowledged"]:
                async_create_critical_repository_issue(self.hass, critical)

        # Keeping installed repositories up to date takes a connected account,
        # the catalog comes from the data feed.
        if self.github_connected:
            self._async_track_interval(
                self.async_update_installed_custom_repositories, timedelta(hours=48)
            )

        self._async_track_interval(
            self.async_get_all_category_repositories, timedelta(hours=6)
        )
        self._async_track_interval(
            self.async_handle_removed_repositories, timedelta(hours=6)
        )

        if self.github_connected:
            self._async_track_interval(
                self.async_check_rate_limit, timedelta(minutes=5)
            )
            self._async_track_interval(self.async_process_queue, timedelta(minutes=10))

        self._async_track_interval(
            self.async_handle_critical_repositories, timedelta(hours=6)
        )

        self.configuration.config_entry.async_on_unload(
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_FINAL_WRITE, self.data.async_force_write
            )
        )

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
        url: str | None,
        *,
        nolog: bool = False,
        handle_rate_limit: bool = False,
    ) -> bytes | None:
        """Download a file, retrying on timeouts and rate limits."""
        if url is None:
            return None

        LOGGER.debug("Trying to download %s", url)
        attempt_count = 0

        while attempt_count < 5:
            try:
                async with self.session.get(
                    url=url, timeout=DOWNLOAD_TIMEOUT
                ) as response:
                    if response.status == 200:
                        return await async_read_limited(response, url)

                    status = response.status
                    retry_after_header = response.headers.get("retry-after")
            except TimeoutError:
                LOGGER.warning(
                    "Downloading %s timed out, %s tries left",
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

            if handle_rate_limit and status == 429:
                try:
                    header = int(retry_after_header or 10)
                except ValueError, TypeError:
                    header = 10
                retry_after = min(header, 60)

                LOGGER.warning(
                    "GitHub has imposed a ratelimit on the request for %s, "
                    "retrying after %s seconds",
                    url,
                    retry_after,
                )
                attempt_count += 1
                await asyncio.sleep(retry_after)
                continue

            if not nolog:
                LOGGER.error(
                    "Got status code %s when trying to download %s", status, url
                )
            return None
        return None

    async def async_wait_for_installs(self) -> None:
        """Wait for the installs that are running to finish."""
        for repository in self.repositories.list_all:
            await repository.async_wait_for_install()

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

        if self.hass.services.has_service(
            "frontend", "reload_themes"
        ) or self.repositories.category_installed(RepositoryCategory.THEME):
            self.enable_category(RepositoryCategory.THEME)

    async def async_get_all_category_repositories(
        self, _: datetime | None = None
    ) -> None:
        """Get all category repositories."""
        if self.system.removed:
            return
        LOGGER.info("Loading known repositories")
        await asyncio.gather(
            *[
                self.async_get_category_repositories_from_catalog(category)
                for category in self.common.categories or []
            ]
        )

    async def async_get_category_repositories_from_catalog(
        self, category: RepositoryCategory
    ) -> None:
        """Take over the catalog of one category."""
        LOGGER.debug("Fetching updated content for %s", category)
        try:
            category_data = await self.data_client.async_get_category(category)
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

        category_data = newest_id_per_name(category_data)
        await self.data.register_unknown_repositories(category_data, category)

        for repo_id, repo_data in category_data.items():
            self._async_take_over_catalog_entry(repo_id, repo_data)

        # An answer without one usable entry says nothing about what is stale
        if self.stage == MarketplaceStage.STARTUP and category_data:
            self._async_unregister_stale_custom_repositories(category)

        self.async_dispatch(MarketplaceSignal.REPOSITORY, {})
        self.coordinators[category].async_update_listeners()

    def _async_take_over_catalog_entry(
        self, repo_id: str, repo_data: dict[str, Any]
    ) -> None:
        """Take over what the catalog knows of a repository that is registered."""
        repo_name = self.common.renamed_repositories.get(
            repo_data["full_name"], repo_data["full_name"]
        )
        if (
            self.repositories.is_removed(repo_name)
            or repo_name in self.common.archived_repositories
        ):
            return

        repository = self.repositories.get_by_full_name(repo_name)
        # Renamed on GitHub, the id is the one thing the catalog keeps
        if repository is None and (repository := self.repositories.get_by_id(repo_id)):
            self.common.renamed_repositories[repository.data.full_name] = repo_name
            self.repositories.rename(repository, repo_name)
        if repository is None:
            return

        self.async_set_repository_id(repository, repo_id)
        self.repositories.mark_default(repository)

        if repository.data.last_fetched is None or (
            repository.data.last_fetched.timestamp() < repo_data["last_fetched"]
        ):
            update = {**dict(REPOSITORY_KEYS_TO_EXPORT), **repo_data}
            # The files on disk are where the install put them, removal goes by
            # this domain
            if repository.data.installed:
                update.pop("domain", None)
            repository.data.update_data(update)
            if (manifest := repo_data.get("manifest")) is not None:
                repository.repository_manifest.update_data(
                    {**dict(REPOSITORY_MANIFEST_KEYS_TO_EXPORT), **manifest}
                )
        elif not repository.data.installed:
            # Storage keeps versions for installed repositories only
            repository.data.last_version = repo_data.get("last_version")
            repository.data.last_commit = repo_data.get("last_commit")

    def _async_unregister_stale_custom_repositories(
        self, category: RepositoryCategory
    ) -> None:
        """Unregister what the catalog no longer lists and nobody added by hand."""
        for repository in self.repositories.list_all:
            repository_id = repository.data.id
            if (
                repository.data.category == category
                and not repository.data.installed
                and not self.repositories.is_default(repository_id)
                and repository_id not in self.common.custom_repositories
            ):
                repository.logger.debug(
                    "%s Unregister stale custom repository", repository.string
                )
                self.repositories.unregister(repository)

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
        if not self.github_connected:
            LOGGER.debug("No GitHub account connected, not processing the queue")
            return
        if self.system.disabled:
            LOGGER.debug("The Marketplace is disabled")
            return
        if not self.queue.has_pending_tasks:
            LOGGER.debug("Nothing in the queue")
            return
        if self.queue.running:
            LOGGER.debug("Queue is already running")
            return

        while self.queue.pending_tasks:
            can_update = await self.async_can_update()
            LOGGER.debug(
                "Can update %s repositories, items in queue %s",
                can_update,
                self.queue.pending_tasks,
            )
            if can_update == 0:
                return

            try:
                await self.queue.execute(can_update)
            except ExecutionInProgressError:
                return

        await self.data.async_write()

    async def async_handle_removed_repositories(
        self, _: datetime | None = None
    ) -> None:
        """Handle removed repositories."""
        if self.system.removed:
            return
        need_to_save = False
        LOGGER.info("Loading removed repositories")

        try:
            removed_repositories = await self.data_client.async_get_removed()
        except MarketplaceError:
            return

        for item in removed_repositories:
            removed = self.repositories.removed_repository(item["repository"])
            removed.update_data(item)

        for removed in self.repositories.list_removed:
            repository = self.repositories.get_by_full_name(removed.repository)
            if (
                repository is None
                or repository.data.full_name in self.common.ignored_repositories
            ):
                continue

            if not repository.data.installed:
                need_to_save = True
                repository.remove()
            # A critical removal uninstalls on its own, with its own repair
            elif removed.removal_type != "critical":
                self._async_create_removed_issue(repository, removed)

        if need_to_save:
            await self.data.async_write()

    def _async_create_removed_issue(
        self, repository: Repository, removed: RemovedRepository
    ) -> None:
        """Tell the user a repository they installed was removed from the catalog."""
        placeholders = {
            "name": repository.data.full_name,
            "repository_id": repository.data.id,
        }
        # Many removals come without one, "None" is no reason
        if removed.reason:
            placeholders["reason"] = removed.reason
        async_create_issue(
            hass=self.hass,
            domain=DOMAIN,
            issue_id=f"removed_{repository.data.id}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="removed" if removed.reason else "removed_without_reason",
            translation_placeholders=placeholders,
        )
        LOGGER.warning(
            "You have '%s' installed with the Marketplace, "
            "this repository has been removed, please consider removing it. "
            "Removal reason (%s)",
            repository.data.full_name,
            removed.reason,
        )

    async def async_update_installed_custom_repositories(
        self, _: datetime | None = None
    ) -> None:
        """Queue an update of every installed custom repository."""
        if self.system.disabled or not self.github_connected:
            return
        LOGGER.info(
            "Starting recurring background task for installed custom repositories"
        )

        repositories_to_update = 0
        repositories_updated = asyncio.Event()

        async def update_repository(repository: Repository) -> None:
            """Update a repository."""
            nonlocal repositories_to_update
            try:
                await repository.update_repository(ignore_issues=True)
            finally:
                # A repository that fails still counts, or the wait never ends
                repositories_to_update -= 1
                if not repositories_to_update:
                    repositories_updated.set()

        for repository in self.repositories.list_installed:
            if (
                repository.data.category in self.common.categories
                and not self.repositories.is_default(repository.data.id)
            ):
                repositories_to_update += 1
                self.queue.add(update_repository(repository))

        if not repositories_to_update:
            return

        async def update_coordinators() -> None:
            """Update all coordinators."""
            await repositories_updated.wait()
            for coordinator in self.coordinators.values():
                coordinator.async_update_listeners()

        self.configuration.config_entry.async_create_background_task(
            self.hass, update_coordinators(), "update_coordinators"
        )

        LOGGER.debug("Recurring background task for installed custom repositories done")

    async def async_handle_critical_repositories(
        self, _: datetime | None = None
    ) -> None:
        """Handle critical repositories."""
        critical: list[dict[str, Any]] = []
        was_installed = False

        try:
            critical = await self.data_client.async_get_critical()
        except GitHubNotModifiedException, NotModifiedError:
            # Unchanged, still checked: a removal that failed before is tried again
            critical = self.critical_repositories
        except MarketplaceError:
            pass
        else:
            self.critical_repositories = critical

        if not critical:
            LOGGER.debug("No critical repositories")
            return

        previously_stored = {
            stored["repository"]: stored
            for stored in await async_load_from_storage(self.hass, "critical") or []
        }
        stored_critical = []

        for entry in critical:
            full_name = entry["repository"]
            removed = self.repositories.removed_repository(full_name)
            removed.removal_type = "critical"
            repository = self.repositories.get_by_full_name(full_name)

            previous = previously_stored.get(full_name)
            stored = {
                "repository": full_name,
                "reason": entry["reason"],
                "link": entry["link"],
                # Confirming the repair is what acknowledges a removal
                "acknowledged": previous["acknowledged"] if previous else True,
            }
            if (
                previous is None
                and repository is not None
                and repository.data.installed
            ):
                LOGGER.critical(
                    "Removing repository %s, it is marked as critical", full_name
                )
                await repository.async_wait_for_install()
                try:
                    await repository.uninstall()
                except MarketplaceError as exception:
                    # Not recorded, the next check tries to remove it again
                    LOGGER.error(
                        "Could not remove critical repository %s: %s",
                        full_name,
                        exception,
                    )
                    continue
                was_installed = True
                stored["acknowledged"] = False
                repository.remove()
                async_create_critical_repository_issue(self.hass, stored)

            stored_critical.append(stored)
            removed.update_data(stored)

        await async_save_to_storage(self.hass, "critical", stored_critical)

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
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="not_loaded"
        )

    entry: MarketplaceConfigEntry = entries[0]
    return entry.runtime_data
