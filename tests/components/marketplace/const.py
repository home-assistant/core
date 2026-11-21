"""Constants for the Marketplace tests."""

import pytest

from homeassistant.components.marketplace.enums import RepositoryCategory

TOKEN = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

# How the admin user of the tests accepted the first-run warning, unless they
# opt out.
WARNING_ACCEPTANCE = {
    "version": 1,
    "accepted_at": "2026-09-01T12:00:00+00:00",
}

# The instant HACS recorded the fixtures at. Several of them carry absolute
# `last_fetched` timestamps that the staleness checks compare against, so tests
# that depend on those checks have to run at this instant.
FROZEN_TIME = "2019-02-26T15:02:39+00:00"

REPOSITORY_INTEGRATION_ID = "1296269"
REPOSITORY_INTEGRATION = "hacs-test-org/integration-basic"

# Commits of the recorded integration repository, and one only its fork holds
COMMIT_ON_MAIN = "1111111111111111111111111111111111111111"
COMMIT_ON_FEATURE = "2222222222222222222222222222222222222222"
COMMIT_ON_FORK = "3333333333333333333333333333333333333333"
COMMIT_MISSING = "0123456789abcdef0123456789abcdef01234567"

# Refs that are not a branch, tag or branch commit of the repository. GitHub
# serves pull requests, also those from forks, under the name of the repository.
NOT_UPSTREAM_VERSIONS = (
    pytest.param("pull/1/head", id="pull_request_head"),
    pytest.param("refs/pull/1/head", id="pull_request_ref"),
    pytest.param("pull/1/merge", id="pull_request_merge"),
    pytest.param(COMMIT_ON_FORK, id="commit_on_fork"),
    pytest.param(COMMIT_ON_FORK[:7], id="short_commit_on_fork"),
    pytest.param(COMMIT_MISSING, id="missing_commit"),
    pytest.param("9.9.9", id="missing_tag"),
)

REPOSITORY_PLUGIN_ID = "1296267"
REPOSITORY_PLUGIN = "hacs-test-org/plugin-basic"

# The recorded responses all came back with a rate limit that never runs out
# and the same etag, which is what the etag bookkeeping is checked against.
PROXY_HEADERS = {
    "Content-Type": "application/json",
    "Etag": "321",
    "X-RateLimit-Limit": "999",
    "X-RateLimit-Remaining": "999",
    "X-RateLimit-Reset": "999",
}

# The categories that are always active, regardless of what is installed.
DEFAULT_CATEGORIES = {
    RepositoryCategory.INTEGRATION,
    RepositoryCategory.PLUGIN,
    RepositoryCategory.TEMPLATE,
}
