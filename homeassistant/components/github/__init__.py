"""The GitHub integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict, List

from aiogithubapi import (
    AIOGitHubAPIAuthenticationException,
    AIOGitHubAPIException,
    GitHub,
)
from aiogithubapi.objects.repos.commit import AIOGitHubAPIReposCommit
from aiogithubapi.objects.repos.traffic.clones import AIOGitHubAPIReposTrafficClones
from aiogithubapi.objects.repos.traffic.pageviews import (
    AIOGitHubAPIReposTrafficPageviews,
)
from aiogithubapi.objects.repository import (
    AIOGitHubAPIRepository,
    AIOGitHubAPIRepositoryIssue,
    AIOGitHubAPIRepositoryRelease,
)
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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


class GitHubData:
    """Represents a GitHub data object."""

    def __init__(
        self,
        repository: AIOGitHubAPIRepository,
        latest_commit: AIOGitHubAPIReposCommit = None,
        clones: AIOGitHubAPIReposTrafficClones = None,
        issues: List[AIOGitHubAPIRepositoryIssue] = None,
        releases: List[AIOGitHubAPIRepositoryRelease] = None,
        views: AIOGitHubAPIReposTrafficPageviews = None,
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
        try:
            async with async_timeout.timeout(60):
                repository: AIOGitHubAPIRepository = await github.get_repo(
                    entry.data[CONF_REPOSITORY]
                )
                if entry.options.get(CONF_LATEST_COMMIT, True) is True:
                    latest_commit: AIOGitHubAPIReposCommit = await repository.get_last_commit()
                else:
                    latest_commit = None
                if entry.options.get(CONF_ISSUES_PRS, False) is True:
                    issues: List[
                        AIOGitHubAPIRepositoryIssue
                    ] = await repository.get_issues()
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
                        clones: AIOGitHubAPIReposTrafficClones = await repository.traffic.get_clones()
                    else:
                        clones = None
                    if entry.options.get(CONF_VIEWS, False) is True:
                        views: AIOGitHubAPIReposTrafficPageviews = await repository.traffic.get_views()
                    else:
                        views = None
                else:
                    clones = None
                    views = None

                return GitHubData(
                    repository, latest_commit, clones, issues, releases, views
                )
        except (AIOGitHubAPIAuthenticationException, AIOGitHubAPIException) as err:
            raise UpdateFailed(f"Error communicating with GitHub: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name=DOMAIN,
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=120),
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

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

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
