"""Custom data update coordinator for the GitHub integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiogithubapi import (
    GitHubAPI,
    GitHubAuthenticationException,
    GitHubConnectionException,
    GitHubEventModel,
    GitHubException,
    GitHubRatelimitException,
    GitHubResponseModel,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import FALLBACK_UPDATE_INTERVAL, LOGGER, REFRESH_EVENT_TYPES

GRAPHQL_REPOSITORY_QUERY = """
query ($owner: String!, $repository: String!) {
  rateLimit {
    cost
    remaining
  }
  repository(owner: $owner, name: $repository) {
    default_branch_ref: defaultBranchRef {
      commit: target {
        ... on Commit {
          message: messageHeadline
          url
          sha: oid
        }
      }
    }
    stargazers_count: stargazerCount
    forks_count: forkCount
    full_name: nameWithOwner
    id: databaseId
    watchers(first: 1) {
      total: totalCount
    }
    discussion: discussions(
      first: 1
      orderBy: {field: CREATED_AT, direction: DESC}
    ) {
      total: totalCount
      discussions: nodes {
        title
        url
        number
      }
    }
    issue: issues(
      first: 1
      states: OPEN
      orderBy: {field: CREATED_AT, direction: DESC}
    ) {
      total: totalCount
      issues: nodes {
        title
        url
        number
      }
    }
    pull_request: pullRequests(
      first: 1
      states: OPEN
      orderBy: {field: CREATED_AT, direction: DESC}
    ) {
      total: totalCount
      pull_requests: nodes {
        title
        url
        number
      }
    }
    release: latestRelease {
      name
      url
      tag: tagName
    }
    refs(
      first: 1
      refPrefix: "refs/tags/"
      orderBy: {field: TAG_COMMIT_DATE, direction: DESC}
    ) {
      tags: nodes {
        name
        target {
          url: commitUrl
        }
      }
    }
  }
}
"""

GRAPHQL_ACCOUNT_QUERY = """
query {
  viewer {
    login
    issues(first: 1, filterBy: {assignee: "USERNAME", states: OPEN}) {
      totalCount
    }
    pullRequests(first: 1, states: OPEN) {
      totalCount
    }
  }
}
"""


@dataclass
class GitHubRuntimeData:
    """Class to hold your data."""

    repositories: dict[str, GitHubDataUpdateCoordinator]
    account: GitHubAccountDataUpdateCoordinator


type GithubConfigEntry = ConfigEntry[GitHubRuntimeData]


class GitHubDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data update coordinator for the GitHub integration."""

    config_entry: GithubConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GithubConfigEntry,
        client: GitHubAPI,
        repository: str,
    ) -> None:
        """Initialize GitHub data update coordinator base class."""
        self.repository = repository
        self._client = client
        self._last_response: GitHubResponseModel[dict[str, Any]] | None = None
        self._subscription_id: str | None = None
        self.data = {}

        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=repository,
            update_interval=FALLBACK_UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> GitHubResponseModel[dict[str, Any]]:
        """Update data."""
        owner, repository = self.repository.split("/")
        try:
            response = await self._client.graphql(
                query=GRAPHQL_REPOSITORY_QUERY,
                variables={"owner": owner, "repository": repository},
            )
        except (GitHubConnectionException, GitHubRatelimitException) as exception:
            # These are expected and we dont log anything extra
            raise UpdateFailed(exception) from exception
        except GitHubException as exception:
            # These are unexpected and we log the trace to help with troubleshooting
            LOGGER.exception(exception)
            raise UpdateFailed(exception) from exception

        self._last_response = response
        return response.data["data"]["repository"]

    async def _handle_event(self, event: GitHubEventModel) -> None:
        """Handle an event."""
        if event.type in REFRESH_EVENT_TYPES:
            await self.async_request_refresh()

    @staticmethod
    async def _handle_error(error: GitHubException) -> None:
        """Handle an error."""
        LOGGER.error("An error occurred while processing new events - %s", error)

    async def subscribe(self) -> None:
        """Subscribe to repository events."""
        self._subscription_id = await self._client.repos.events.subscribe(
            self.repository,
            event_callback=self._handle_event,
            error_callback=self._handle_error,
        )
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.unsubscribe)

    def unsubscribe(self, *args: Any) -> None:
        """Unsubscribe to repository events."""
        self._client.repos.events.unsubscribe(subscription_id=self._subscription_id)


class GitHubAccountDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data update coordinator for the GitHub account."""

    config_entry: GithubConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GithubConfigEntry,
        client: GitHubAPI,
    ) -> None:
        """Initialize GitHub data update coordinator base class."""
        self._client = client
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"GitHub Account {config_entry.title}",
            update_interval=FALLBACK_UPDATE_INTERVAL,
        )
        self.data = {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data."""
        data: dict[str, Any] = {}

        try:
            # Notifications
            # Fetch unread notifications
            # Use generic for notifications endpoint
            try:
                notifications = await self._client.generic("/notifications")
                data["notifications"] = {
                    "count": len(notifications.data),
                    "items": [
                        {
                            "title": n["subject"]["title"],
                            "repository": n["repository"]["full_name"],
                            "url": n["repository"]["html_url"],
                            "type": n["subject"]["type"],
                        }
                        for n in notifications.data[:5]
                    ],
                }
            except GitHubAuthenticationException:
                data["notifications"] = None
                LOGGER.warning(
                    "GitHub Personal Access Token is missing 'notifications' scope"
                )

            # Helper to extract search items
            def _extract_search_items(search_result: Any) -> list[dict[str, Any]]:
                return [
                    {
                        "title": item["title"],
                        "number": item["number"],
                        "url": item["html_url"],
                        "repository": item["repository_url"].split("/repos/", 1)[1],
                    }
                    for item in search_result.data["items"][:5]
                ]

            # Assigned Issues
            issues = await self._client.generic(
                "/search/issues", params={"q": "is:open is:issue assignee:@me"}
            )
            data["issues"] = {
                "count": issues.data["total_count"],
                "items": _extract_search_items(issues),
            }

            # Assigned PRs
            prs = await self._client.generic(
                "/search/issues", params={"q": "is:open is:pr assignee:@me"}
            )
            data["pull_requests"] = {
                "count": prs.data["total_count"],
                "items": _extract_search_items(prs),
            }

            # Review Requests
            reviews = await self._client.generic(
                "/search/issues", params={"q": "is:open is:pr review-requested:@me"}
            )
            data["review_requests"] = {
                "count": reviews.data["total_count"],
                "items": _extract_search_items(reviews),
            }

        except (GitHubConnectionException, GitHubRatelimitException) as exception:
            raise UpdateFailed(exception) from exception
        except GitHubException as exception:
            LOGGER.exception(exception)
            raise UpdateFailed(exception) from exception

        return data
