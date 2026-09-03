"""Enums for the Community store."""

from enum import StrEnum
from typing import override


class RepositoryCategory(StrEnum):
    """Repository categories the store knows about."""

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


class StoreSignal(StrEnum):
    """Dispatcher signals the store sends."""

    CONFIG = "store_config"
    ERROR = "store_error"
    RELOAD = "store_reload"
    REPOSITORY = "store_repository"
    REPOSITORY_DOWNLOAD_PROGRESS = "store_repository_download_progress"
    STAGE = "store_stage"
    STARTUP = "store_startup"
    STATUS = "store_status"


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


class StoreStage(StrEnum):
    """Stages the store moves through during its lifetime."""

    SETUP = "setup"
    STARTUP = "startup"
    WAITING = "waiting"
    RUNNING = "running"


class DisabledReason(StrEnum):
    """Reasons why the store can be disabled."""

    RATE_LIMIT = "rate_limit"
    REMOVED = "removed"
    INVALID_TOKEN = "invalid_token"
