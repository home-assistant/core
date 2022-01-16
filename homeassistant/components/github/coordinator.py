"""Custom data update coordinators for the GitHub integration."""
from __future__ import annotations

import asyncio
from typing import Literal, TypedDict

from aiogithubapi import (
    GitHubAPI,
    GitHubCommitModel,
    GitHubException,
    GitHubIssueModel,
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
        return result.data[0] if result.data else None


class RepositoryIssueDataUpdateCoordinator(
    GitHubBaseDataUpdateCoordinator[IssuesPulls]
):
    """Data update coordinator for repository issues."""

    async def fetch_data(self) -> IssuesPulls:
        """Get the latest data from GitHub."""

        async def _get_issues():
            response = await self._client.repos.issues.list(
                self.repository, **{"params": {"per_page": 100}}
            )
            if not response.is_last_page:
                results = await asyncio.gather(
                    *(
                        self._client.repos.issues.list(
                            self.repository,
                            **{"params": {"per_page": 100, "page": page_number}},
                        )
                        for page_number in range(
                            response.next_page_number, response.last_page_number + 1
                        )
                    )
                )
                for result in results:
                    response.data.extend(result.data)

            return response.data

        all_issues = await _get_issues()

        issues: list[GitHubIssueModel] = [
            issue for issue in all_issues or [] if issue.pull_request is None
        ]
        pulls: list[GitHubIssueModel] = [
            issue for issue in all_issues or [] if issue.pull_request is not None
        ]

        return IssuesPulls(issues=issues, pulls=pulls)


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
