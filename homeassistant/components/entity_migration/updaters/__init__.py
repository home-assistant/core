"""File updaters for entity migration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.components.entity_migration.models import UpdateResult


class BaseUpdater(ABC):
    """Abstract base class for file updaters."""

    @abstractmethod
    async def async_update(
        self,
        file_path: Path,
        old_entity_id: str,
        new_entity_id: str,
        *,
        dry_run: bool = False,
    ) -> UpdateResult:
        """Update entity references in a file.

        Args:
            file_path: Path to the file to update.
            old_entity_id: The entity ID to replace.
            new_entity_id: The new entity ID.
            dry_run: If True, don't actually write changes.

        Returns:
            UpdateResult with success status and changes made.
        """

    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """Check if this updater can handle the given file.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if this updater can handle the file.
        """


# Import concrete updaters for convenience
from homeassistant.components.entity_migration.updaters.json_updater import (  # noqa: E402
    JSONStorageUpdater,
)
from homeassistant.components.entity_migration.updaters.yaml_updater import (  # noqa: E402
    YAMLFileUpdater,
)

__all__ = [
    "BaseUpdater",
    "JSONStorageUpdater",
    "YAMLFileUpdater",
]
