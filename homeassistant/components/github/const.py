"""Constants for the GitHub integration."""
from __future__ import annotations

from datetime import timedelta
from logging import Logger, getLogger
from typing import NamedTuple

from aiogithubapi import GitHubIssueModel

LOGGER: Logger = getLogger(__package__)

DOMAIN = "github"

CLIENT_ID = "1440cafcc86e3ea5d6a2"

DEFAULT_REPOSITORIES = ["home-assistant/core", "esphome/esphome"]
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=300)

CONF_ACCESS_TOKEN = "access_token"
CONF_REPOSITORIES = "repositories"


class IssuesPulls(NamedTuple):
    """Issues and pull requests."""

    issues_count: int
    issue_last: GitHubIssueModel | None
    pulls_count: int
    pull_last: GitHubIssueModel | None
