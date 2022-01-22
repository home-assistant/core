"""Custom data update coordinators for the GitHub integration."""
from __future__ import annotations

from typing import Literal, TypedDict

from aiogithubapi import (
    GitHubAPI,
    GitHubCommitModel,
    GitHubException,
    GitHubReleaseModel,
    GitHubRepositoryModel,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, T
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, LOGGER, IssuesPulls

CoordinatorKeyType = Literal["information", "release", "issue", "commit"]


class GitHubBaseDataUpdateCoordinator(DataUpdateCoordinator[T]):
    """Base class for GitHub data update coordinators."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GitHubAPI,
        repository: str,
    ) -> None:
        """Initialize GitHub data update coordinator base class."""
        self.config_entry = entry
        self.repository = repository
        self._client = client

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

    async def fetch_data(self) -> T:
        """Fetch data from GitHub API."""

    async def _async_update_data(self) -> T:
        try:
            return await self.fetch_data()
        except GitHubException as exception:
            LOGGER.exception(exception)
            raise UpdateFailed(exception) from exception


class RepositoryInformationDataUpdateCoordinator(
    GitHubBaseDataUpdateCoordinator[GitHubRepositoryModel]
):
    """Data update coordinator for repository information."""

    async def fetch_data(self) -> GitHubRepositoryModel:
        """Get the latest data from GitHub."""
        result = await self._client.repos.get(self.repository)
        return result.data


class RepositoryReleaseDataUpdateCoordinator(
    GitHubBaseDataUpdateCoordinator[GitHubReleaseModel]
):
    """Data update coordinator for repository release."""

    async def fetch_data(self) -> GitHubReleaseModel | None:
        """Get the latest data from GitHub."""
        result = await self._client.repos.releases.list(
            self.repository, **{"params": {"per_page": 1}}
        )
        if not result.data:
            return None

        for release in result.data:
            if not release.prerelease:
                return release

        # Fall back to the latest release if no non-prerelease release is found
        return result.data[0]


class RepositoryIssueDataUpdateCoordinator(
    GitHubBaseDataUpdateCoordinator[IssuesPulls]
):
    """Data update coordinator for repository issues."""

    async def fetch_data(self) -> IssuesPulls:
        """Get the latest data from GitHub."""
        base_issue_response = await self._client.repos.issues.list(
            self.repository, **{"params": {"per_page": 1}}
        )
        pull_response = await self._client.repos.pulls.list(
            self.repository, **{"params": {"per_page": 1}}
        )

        pulls_count = pull_response.last_page_number or 0
        issues_count = (base_issue_response.last_page_number or 0) - pulls_count

        issue_last = base_issue_response.data[0] if issues_count != 0 else None

        if issue_last is not None and issue_last.pull_request:
            issue_response = await self._client.repos.issues.list(self.repository)
            for issue in issue_response.data:
                if not issue.pull_request:
                    issue_last = issue
                    break

        return IssuesPulls(
            issues_count=issues_count,
            issue_last=issue_last,
            pulls_count=pulls_count,
            pull_last=pull_response.data[0] if pulls_count != 0 else None,
        )


class RepositoryCommitDataUpdateCoordinator(
    GitHubBaseDataUpdateCoordinator[GitHubCommitModel]
):
    """Data update coordinator for repository commit."""

    async def fetch_data(self) -> GitHubCommitModel | None:
        """Get the latest data from GitHub."""
        result = await self._client.repos.list_commits(
            self.repository, **{"params": {"per_page": 1}}
        )
        return result.data[0] if result.data else None


class DataUpdateCoordinators(TypedDict):
    """Custom data update coordinators for the GitHub integration."""

    information: RepositoryInformationDataUpdateCoordinator
    release: RepositoryReleaseDataUpdateCoordinator
    issue: RepositoryIssueDataUpdateCoordinator
    commit: RepositoryCommitDataUpdateCoordinator
