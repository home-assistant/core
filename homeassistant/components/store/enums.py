"""Helper constants."""

from enum import StrEnum
from typing import override


class HacsGitHubRepo(StrEnum):
    """HacsGitHubRepo."""

    DEFAULT = "hacs/default"
    INTEGRATION = "hacs/integration"


class HacsCategory(StrEnum):
    """Repository categories HACS knows about."""

    APPDAEMON = "appdaemon"
    INTEGRATION = "integration"
    PLUGIN = "plugin"  # Kept for legacy purposes
    PYTHON_SCRIPT = "python_script"
    TEMPLATE = "template"
    THEME = "theme"

    @override
    def __str__(self) -> str:
        """Return the string representation."""
        return str(self.value)


class HacsDispatchEvent(StrEnum):
    """HacsDispatchEvent."""

    CONFIG = "hacs_dispatch_config"
    ERROR = "hacs_dispatch_error"
    RELOAD = "hacs_dispatch_reload"
    REPOSITORY = "hacs_dispatch_repository"
    REPOSITORY_DOWNLOAD_PROGRESS = "hacs_dispatch_repository_download_progress"
    STAGE = "hacs_dispatch_stage"
    STARTUP = "hacs_dispatch_startup"
    STATUS = "hacs_dispatch_status"


class RepositoryFile(StrEnum):
    """Repository file names."""

    HACS_JSON = "hacs.json"
    MAINIFEST_JSON = "manifest.json"


class LovelaceMode(StrEnum):
    """Lovelace Modes."""

    STORAGE = "storage"
    AUTO = "auto"
    AUTO_GEN = "auto-gen"
    YAML = "yaml"


class HacsStage(StrEnum):
    """Stages HACS moves through during its lifetime."""

    SETUP = "setup"
    STARTUP = "startup"
    WAITING = "waiting"
    RUNNING = "running"


class HacsDisabledReason(StrEnum):
    """Reasons why HACS can be disabled."""

    RATE_LIMIT = "rate_limit"
    REMOVED = "removed"
    INVALID_TOKEN = "invalid_token"
    CONSTRAINS = "constrains"
    LOAD_HACS = "load_hacs"
    RESTORE = "restore"
