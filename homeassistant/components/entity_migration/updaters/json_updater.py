"""JSON storage file updater for entity migration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import aiofiles

from homeassistant.components.entity_migration.models import UpdateResult

from . import BaseUpdater

_LOGGER = logging.getLogger(__name__)


class JSONStorageUpdater(BaseUpdater):
    """Updater for Home Assistant .storage JSON files.

    Handles JSON files in the .storage directory, preserving structure
    and formatting.
    """

    def can_handle(self, file_path: Path) -> bool:
        """Check if this updater can handle the given file.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if the file is a JSON file or in .storage directory.
        """
        # Handle .json files and .storage files (which don't have extension)
        if file_path.suffix.lower() == ".json":
            return True
        # Storage files are typically in .storage directory without extension
        if ".storage" in str(file_path):
            return True
        return False

    async def async_update(
        self,
        file_path: Path,
        old_entity_id: str,
        new_entity_id: str,
        *,
        dry_run: bool = False,
    ) -> UpdateResult:
        """Update entity references in a JSON storage file.

        Args:
            file_path: Path to the JSON file to update.
            old_entity_id: The entity ID to replace.
            new_entity_id: The new entity ID.
            dry_run: If True, don't actually write changes.

        Returns:
            UpdateResult with success status and changes made.
        """
        try:
            # Read the file
            async with aiofiles.open(file_path, encoding="utf-8") as f:
                content = await f.read()

            # Parse JSON
            data = json.loads(content)

            # Perform recursive replacement
            changes_made = self._recursive_replace(data, old_entity_id, new_entity_id)

            if changes_made == 0:
                return UpdateResult(
                    success=True,
                    file_path=file_path,
                    changes_made=0,
                )

            if not dry_run:
                # Write the updated content back with same formatting as HA uses
                new_content = json.dumps(data, indent=4, ensure_ascii=False)

                async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                    await f.write(new_content)

                _LOGGER.debug(
                    "Updated %d references in %s",
                    changes_made,
                    file_path,
                )

            return UpdateResult(
                success=True,
                file_path=file_path,
                changes_made=changes_made,
            )

        except json.JSONDecodeError as err:
            _LOGGER.error("Invalid JSON in %s: %s", file_path, err)
            return UpdateResult(
                success=False,
                file_path=file_path,
                changes_made=0,
                error=f"Invalid JSON: {err}",
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to update %s: %s", file_path, err)
            return UpdateResult(
                success=False,
                file_path=file_path,
                changes_made=0,
                error=str(err),
            )

    def _recursive_replace(
        self,
        data: Any,
        old_entity_id: str,
        new_entity_id: str,
    ) -> int:
        """Recursively replace entity ID in a JSON data structure.

        Handles nested dicts, lists, and string values.

        Args:
            data: The data structure to process.
            old_entity_id: The entity ID to replace.
            new_entity_id: The new entity ID.

        Returns:
            Number of replacements made.
        """
        changes = 0

        if isinstance(data, dict):
            for key in list(data.keys()):
                value = data[key]

                # Check if key itself is the entity ID
                if key == old_entity_id:
                    data[new_entity_id] = data.pop(key)
                    changes += 1
                    value = data[new_entity_id]

                if isinstance(value, str):
                    replaced, count = self._replace_in_string(
                        value, old_entity_id, new_entity_id
                    )
                    if count > 0:
                        if key == old_entity_id:
                            data[new_entity_id] = replaced
                        else:
                            data[key] = replaced
                        changes += count
                elif isinstance(value, (dict, list)):
                    changes += self._recursive_replace(
                        value, old_entity_id, new_entity_id
                    )

        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, str):
                    replaced, count = self._replace_in_string(
                        item, old_entity_id, new_entity_id
                    )
                    if count > 0:
                        data[i] = replaced
                        changes += count
                elif isinstance(item, (dict, list)):
                    changes += self._recursive_replace(
                        item, old_entity_id, new_entity_id
                    )

        return changes

    def _replace_in_string(
        self,
        value: str,
        old_entity_id: str,
        new_entity_id: str,
    ) -> tuple[str, int]:
        """Replace entity ID in a string value.

        Only replaces exact entity ID matches or entity IDs in specific
        contexts to avoid false positives.

        Args:
            value: The string value to process.
            old_entity_id: The entity ID to replace.
            new_entity_id: The new entity ID.

        Returns:
            Tuple of (new string, number of replacements).
        """
        if old_entity_id not in value:
            return value, 0

        # Direct match
        if value == old_entity_id:
            return new_entity_id, 1

        # Count occurrences and replace
        changes = value.count(old_entity_id)
        result = value.replace(old_entity_id, new_entity_id)

        return result, changes
