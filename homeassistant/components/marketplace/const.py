"""Constants for the Marketplace."""

from datetime import timedelta
from typing import TYPE_CHECKING, TypeVar

from homeassistant.const import __version__ as HAVERSION
from homeassistant.util.signal_type import SignalType

if TYPE_CHECKING:
    from .repositories.base import Repository

DOMAIN = "marketplace"
CLIENT_ID = "395a8e669c5de9f7c6e8"
CLIENT_NAME = f"HomeAssistantMarketplace/{HAVERSION}"

# Installed dashboard resources live in www/community, which the frontend
# serves as /local.
DASHBOARD_RESOURCE_BASE = "/local/community"
LEGACY_DASHBOARD_RESOURCE_BASE = "/hacsfiles"

TV = TypeVar("TV")

# A first install, the platforms add the entities of that repository. Not one
# of the signals the panel subscribes to, it carries the repository itself.
SIGNAL_REPOSITORY_INSTALLED: SignalType[Repository] = SignalType(
    "marketplace_repository_installed"
)

PACKAGE_NAME = "homeassistant.components.marketplace"

DEFAULT_CONCURRENT_TASKS = 15

# How many releases are fetched to offer as versions to install
RELEASE_LIMIT = 5

# Ceiling for anything downloaded from a repository, both for the transferred
# bytes and for the size a ZIP archive expands to.
MAX_DOWNLOAD_SIZE = 100 * 1024 * 1024
# Countless empty entries stay under the size ceiling, but take ages to go through
MAX_ARCHIVE_MEMBERS = 50_000
DOWNLOAD_CHUNK_SIZE = 64 * 1024

LEGACY_HACS_REPOSITORY_ID = "172733314"

# The catalog the Marketplace consumes, and the repository of the integration
# it replaces
CATALOG_REPOSITORY = "hacs/default"
LEGACY_HACS_INTEGRATION_REPOSITORY = "hacs/integration"

STORAGE_VERSION = 1

# The version the custom integration wrote its storage files with
LEGACY_HACS_STORAGE_VERSION = "6"

LEGACY_HACS_SYSTEM_ID = (
    "0717a0cd-745c-48fd-9b16-c8534c9704f9-bc944b0f-fd42-4a58-a072-ade38d1444cd"
)

# Bump when the first-run warning changes enough that everyone has to read it
# again, an acceptance of an older version no longer counts.
WARNING_VERSION = 1
CONF_WARNING_ACCEPTED = "warning_accepted"

# The panel shows the warning again once an acceptance is this old, installs
# and updates keep working in the meantime.
WARNING_REMINDER_INTERVAL = timedelta(days=90)

# Installs that need a restart get an issue per repository and version
RESTART_ISSUE_PREFIX = "restart_required_"
