"""Constants for the Marketplace tests."""

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

# The categories that are always active, regardless of what is downloaded.
DEFAULT_CATEGORIES = {
    RepositoryCategory.INTEGRATION,
    RepositoryCategory.PLUGIN,
    RepositoryCategory.TEMPLATE,
}
