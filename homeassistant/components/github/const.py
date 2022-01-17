"""Constants for the GitHub integration."""
from datetime import timedelta
from logging import Logger, getLogger
from typing import NamedTuple

from aiogithubapi import GitHubIssueModel

LOGGER: Logger = getLogger(__package__)

DOMAIN = "github"

# THIS NEED TO CHANGE!!!!
CLIENT_ID = "ce3981304697fb012542"
# THIS NEED TO CHANGE!!!!

DEFAULT_REPOSITORIES = ["home-assistant/core", "esphome/esphome"]
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=300)

CONF_ACCESS_TOKEN = "access_token"
CONF_REPOSITORIES = "repositories"


class IssuesPulls(NamedTuple):
    """Issues and pull requests."""

    issues: list[GitHubIssueModel]
    pulls: list[GitHubIssueModel]
