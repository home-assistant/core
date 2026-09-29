"""Enums for the Marketplace."""

from enum import StrEnum
from typing import override


class RepositoryCategory(StrEnum):
    """Repository categories the Marketplace knows about."""

    INTEGRATION = "integration"
    PLUGIN = "plugin"  # Kept for legacy purposes
    TEMPLATE = "template"
    THEME = "theme"

    @override
    def __str__(self) -> str:
        """Return the string representation."""
        return str(self.value)


class MarketplaceSignal(StrEnum):
    """Dispatcher signals the Marketplace sends."""

    CONFIG = "marketplace_config"
    RELOAD = "marketplace_reload"
    REPOSITORY = "marketplace_repository"
    REPOSITORY_INSTALL_PROGRESS = "marketplace_repository_install_progress"
    STAGE = "marketplace_stage"
    STATUS = "marketplace_status"


class RepositoryFile(StrEnum):
    """Repository file names."""

    REPOSITORY_MANIFEST = "hacs.json"
    MAINIFEST_JSON = "manifest.json"


class LovelaceMode(StrEnum):
    """Lovelace Modes."""

    STORAGE = "storage"
    YAML = "yaml"


class MarketplaceStage(StrEnum):
    """Stages the Marketplace moves through during its lifetime."""

    SETUP = "setup"
    STARTUP = "startup"
    WAITING = "waiting"
    RUNNING = "running"


class DisabledReason(StrEnum):
    """Reasons why the Marketplace can be disabled."""

    RATE_LIMIT = "rate_limit"
    REMOVED = "removed"
    INVALID_TOKEN = "invalid_token"
