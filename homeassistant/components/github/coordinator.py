"""Custom data update coordinators for the GitHub integration."""
from __future__ import annotations

from typing import Literal, TypedDict

from aiogithubapi import (
    GitHubAPI,
    GitHubCommitModel,
    GitHubException,
    GitHubNotModifiedException,
    GitHubReleaseModel,
    GitHubRepositoryModel,
    GitHubResponseModel,
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
        self._last_response: GitHubResponseModel[T] | None = None

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

    @property
    def _etag(self) -> str:
        """Return the ETag of the last response."""
        return self._last_response.etag if self._last_response is not None else None

    async def fetch_data(self) -> GitHubResponseModel[T]:
        """Fetch data from GitHub API."""

    @staticmethod
    def _parse_response(response: GitHubResponseModel[T]) -> T:
        """Parse the response from GitHub API."""
        return response.data

    async def _async_update_data(self) -> T:
        try:
            response = await self.fetch_data()
        except GitHubNotModifiedException:
            LOGGER.debug(
                "Content for %s with %s not modified",
                self.repository,
                self.__class__.__name__,
            )
            # Return the last known data if the request result was not modified
            return self.data
        except GitHubException as exception:
            LOGGER.exception(exception)
            raise UpdateFailed(exception) from exception
        else:
            self._last_response = response
            return self._parse_response(response)


class RepositoryInformationDataUpdateCoordinator(
    GitHubBaseDataUpdateCoordinator[GitHubRepositoryModel]
):
    """Data update coordinator for repository information."""

    async def fetch_data(self) -> GitHubResponseModel[GitHubRepositoryModel]:
        """Get the latest data from GitHub."""
        return await self._client.repos.get(self.repository, **{"etag": self._etag})


class RepositoryReleaseDataUpdateCoordinator(
    GitHubBaseDataUpdateCoordinator[GitHubReleaseModel]
):
    """Data update coordinator for repository release."""

    @staticmethod
    def _parse_response(
        response: GitHubResponseModel[GitHubReleaseModel | None],
    ) -> GitHubReleaseModel | None:
        """Parse the response from GitHub API."""
        if response.data is None:
            return None

        for release in response.data:
            if not release.prerelease and not release.draft:
                return release

        # Fall back to the latest release if no non-prerelease release is found
        return response.data[0]

    async def fetch_data(self) -> GitHubReleaseModel | None:
        """Get the latest data from GitHub."""
        return await self._client.repos.releases.list(
            self.repository, **{"etag": self._etag}
        )


class RepositoryIssueDataUpdateCoordinator(
    GitHubBaseDataUpdateCoordinator[IssuesPulls]
):
    """Data update coordinator for repository issues."""

    _issue_etag: str | None = None
    _pull_etag: str | None = None

    @staticmethod
    def _parse_response(response: IssuesPulls) -> IssuesPulls:
        """Parse the response from GitHub API."""
        return response

    async def fetch_data(self) -> IssuesPulls:
        """Get the latest data from GitHub."""
        pulls_count = 0
        pull_last = None
        issues_count = 0
        issue_last = None
        try:
            pull_response = await self._client.repos.pulls.list(
                self.repository,
                **{"params": {"per_page": 1}, "etag": self._pull_etag},
            )
        except GitHubNotModifiedException:
            # Return the last known data if the request result was not modified
            pulls_count = self.data.pulls_count
            pull_last = self.data.pull_last
        else:
            self._pull_etag = pull_response.etag
            pulls_count = pull_response.last_page_number or len(pull_response.data)
            pull_last = pull_response.data[0] if pull_response.data else None

        try:
            issue_response = await self._client.repos.issues.list(
                self.repository,
                **{"params": {"per_page": 1}, "etag": self._issue_etag},
            )
        except GitHubNotModifiedException:
            # Return the last known data if the request result was not modified
            issues_count = self.data.issues_count
            issue_last = self.data.issue_last
        else:
            self._issue_etag = issue_response.etag
            issues_count = (
                issue_response.last_page_number or len(issue_response.data)
            ) - pulls_count
            issue_last = issue_response.data[0] if issue_response.data else None

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
            pull_last=pull_last,
        )


class RepositoryCommitDataUpdateCoordinator(
    GitHubBaseDataUpdateCoordinator[GitHubCommitModel]
):
    """Data update coordinator for repository commit."""

    @staticmethod
    def _parse_response(
        response: GitHubResponseModel[GitHubCommitModel | None],
    ) -> GitHubCommitModel | None:
        """Parse the response from GitHub API."""
        return response.data[0] if response.data else None

    async def fetch_data(self) -> GitHubCommitModel | None:
        """Get the latest data from GitHub."""
        return await self._client.repos.list_commits(
            self.repository, **{"params": {"per_page": 1}, "etag": self._etag}
        )


class DataUpdateCoordinators(TypedDict):
    """Custom data update coordinators for the GitHub integration."""

    information: RepositoryInformationDataUpdateCoordinator
    release: RepositoryReleaseDataUpdateCoordinator
    issue: RepositoryIssueDataUpdateCoordinator
    commit: RepositoryCommitDataUpdateCoordinator
