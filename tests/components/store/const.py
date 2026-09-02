"""Constants for the Community store tests."""

from homeassistant.components.store.enums import HacsCategory

TOKEN = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

# The instant HACS recorded the fixtures at. Several of them carry absolute
# `last_fetched` timestamps that the staleness checks compare against, so tests
# that depend on those checks have to run at this instant.
FROZEN_TIME = "2019-02-26T15:02:39+00:00"

REPOSITORY_INTEGRATION_ID = "1296269"
REPOSITORY_INTEGRATION = "hacs-test-org/integration-basic"

REPOSITORY_PLUGIN_ID = "1296267"
REPOSITORY_PLUGIN = "hacs-test-org/plugin-basic"

# The categories that are always active, regardless of what is downloaded.
DEFAULT_CATEGORIES = {
    HacsCategory.INTEGRATION,
    HacsCategory.PLUGIN,
    HacsCategory.TEMPLATE,
}
