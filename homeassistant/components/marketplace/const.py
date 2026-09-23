"""Constants for the Marketplace."""

from typing import TypeVar

from homeassistant.const import __version__ as HAVERSION

DOMAIN = "marketplace"
CLIENT_ID = "395a8e669c5de9f7c6e8"
CLIENT_NAME = f"HomeAssistantMarketplace/{HAVERSION}"

# Downloaded dashboard resources live in www/community, which the frontend
# serves as /local.
DASHBOARD_RESOURCE_BASE = "/local/community"
LEGACY_DASHBOARD_RESOURCE_BASE = "/hacsfiles"

TV = TypeVar("TV")

PACKAGE_NAME = "homeassistant.components.marketplace"

DEFAULT_CONCURRENT_TASKS = 15
DEFAULT_CONCURRENT_BACKOFF_TIME = 1

# Ceiling for anything downloaded from a repository, both for the transferred
# bytes and for the size a ZIP archive expands to.
MAX_DOWNLOAD_SIZE = 100 * 1024 * 1024

LEGACY_HACS_REPOSITORY_ID = "172733314"

# The catalog the Marketplace consumes, and the repository of the integration
# it replaces
CATALOG_REPOSITORY = "hacs/default"
LEGACY_HACS_INTEGRATION_REPOSITORY = "hacs/integration"

VERSION_STORAGE = "6"

LEGACY_HACS_SYSTEM_ID = (
    "0717a0cd-745c-48fd-9b16-c8534c9704f9-bc944b0f-fd42-4a58-a072-ade38d1444cd"
)

# The country filter that shows the repositories of every country
COUNTRY_ALL = "ALL"
