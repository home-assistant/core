"""The GitHub integration."""
# TODO: Tests
# TODO: Device triggers? (scaffold)
# TODO: Breaking changes (flow, url, options flow, split etc.)
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict, List

from aiogithubapi import (
    AIOGitHubAPIAuthenticationException,
    AIOGitHubAPIException,
    GitHub,
)
from aiogithubapi.objects.repository import (
    AIOGitHubAPIRepository,
    AIOGitHubAPIRepositoryIssue,
    AIOGitHubAPIRepositoryRelease,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_CLONES,
    CONF_ISSUES_PRS,
    CONF_LATEST_COMMIT,
    CONF_LATEST_RELEASE,
    CONF_REPOSITORY,
    CONF_VIEWS,
    DATA_COORDINATOR,
    DATA_REPOSITORY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


class GitHubClones:
    """Represents a GitHub clones object."""

    def __init__(self, count: int, count_uniques: int) -> None:
        """Initialize a GitHub clones object."""
        self.count = count
        self.count_uniques = count_uniques


class GitHubLatestCommit:
    """Represents a GitHub last commit object."""

    def __init__(self, sha: int, message: str) -> None:
        """Initialize a GitHub last commit object."""
        self.sha = sha
        self.sha_short = sha[0:7]
        self.message = message.splitlines()[0]


class GitHubViews:
    """Represents a GitHub views object."""

    def __init__(self, count: int, count_uniques: int) -> None:
        """Initialize a GitHub views object."""
        self.count = count
        self.count_uniques = count_uniques


class GitHubData:
    """Represents a GitHub data object."""

    def __init__(
        self,
        repository: AIOGitHubAPIRepository,
        latest_commit: GitHubLatestCommit = None,
        clones: GitHubClones = None,
        issues: List[AIOGitHubAPIRepositoryIssue] = None,
        releases: List[AIOGitHubAPIRepositoryRelease] = None,
        views: GitHubViews = None,
    ) -> None:
        """Initialize the GitHub data object."""
        self.repository = repository
        self.latest_commit = latest_commit
        self.clones = clones
        self.issues = issues
        self.releases = releases
        self.views = views

        if issues is not None:
            open_issues: List[AIOGitHubAPIRepositoryIssue] = []
            open_pull_requests: List[AIOGitHubAPIRepositoryIssue] = []
            for issue in issues:
                if issue.state == "open":
                    if "pull" in issue.html_url:
                        open_pull_requests.append(issue)
                    else:
                        open_issues.append(issue)

            self.open_issues = open_issues
            self.open_pull_requests = open_pull_requests
        else:
            self.open_issues = None
            self.open_pull_requests = None


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up GitHub integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up GitHub from a config entry."""
    try:
        github = GitHub(entry.data[CONF_ACCESS_TOKEN])
        repository = await github.get_repo(entry.data[CONF_REPOSITORY])
    except (AIOGitHubAPIAuthenticationException, AIOGitHubAPIException):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "reauth"}, data=entry.data
            )
        )
        return False

    async def async_update_data() -> GitHubData:
        """Fetch data from GitHub."""
        repository: AIOGitHubAPIRepository = await github.get_repo(
            entry.data[CONF_REPOSITORY]
        )
        if entry.options.get(CONF_LATEST_COMMIT, True) is True:
            latest_commit = await repository.client.get(
                endpoint=f"/repos/{repository.full_name}/branches/{repository.default_branch}"
            )
        else:
            latest_commit = None
        if entry.options.get(CONF_ISSUES_PRS, False) is True:
            issues: List[AIOGitHubAPIRepositoryIssue] = await repository.get_issues()
        else:
            issues = None
        if entry.options.get(CONF_LATEST_RELEASE, False) is True:
            releases: List[
                AIOGitHubAPIRepositoryRelease
            ] = await repository.get_releases()
        else:
            releases = None
        if repository.attributes.get("permissions").get("push") is True:
            if entry.options.get(CONF_CLONES, False) is True:
                clones = await repository.client.get(
                    endpoint=f"/repos/{repository.full_name}/traffic/clones"
                )
            else:
                clones = None
            if entry.options.get(CONF_VIEWS, False) is True:
                views = await repository.client.get(
                    endpoint=f"/repos/{repository.full_name}/traffic/views"
                )
            else:
                views = None
        else:
            clones = None
            views = None

        return GitHubData(
            repository,
            GitHubLatestCommit(
                latest_commit["commit"]["sha"],
                latest_commit["commit"]["commit"]["message"],
            )
            if latest_commit is not None
            else None,
            GitHubClones(clones["count"], clones["uniques"])
            if clones is not None
            else None,
            issues,
            releases,
            GitHubViews(views["count"], views["uniques"])
            if views is not None
            else None,
        )

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name=DOMAIN,
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=300),
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_REPOSITORY: repository,
    }

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class GitHubEntity(Entity):
    """Defines a GitHub entity."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, unique_id: str, name: str, icon: str
    ) -> None:
        """Set up GitHub Entity."""
        self._coordinator = coordinator
        self._unique_id = unique_id
        self._name = name
        self._icon = icon
        self._available = True

    @property
    def unique_id(self):
        """Return the unique_id of the sensor."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._coordinator.last_update_success and self._available

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    async def async_update(self) -> None:
        """Update GitHub entity."""
        if await self._github_update():
            self._available = True
        else:
            self._available = False

    async def _github_update(self) -> bool:
        """Update GitHub entity."""
        raise NotImplementedError()


class GitHubDeviceEntity(GitHubEntity):
    """Defines a GitHub device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this GitHub instance."""
        data: GitHubData = self._coordinator.data

        return {
            "identifiers": {(DOMAIN, data.repository.full_name)},
            "manufacturer": data.repository.attributes.get("owner").get("login"),
            "name": data.repository.full_name,
        }
