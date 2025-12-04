"""YAML file updater for entity migration."""

from __future__ import annotations

import logging
from pathlib import Path
import re

import aiofiles

from homeassistant.util import yaml as yaml_util

from ..models import UpdateResult
from . import BaseUpdater

_LOGGER = logging.getLogger(__name__)


class YAMLFileUpdater(BaseUpdater):
    """Updater for YAML configuration files.

    Uses text-based replacement to preserve comments and formatting.
    Validates the result using Home Assistant's YAML parser.
    """

    def can_handle(self, file_path: Path) -> bool:
        """Check if this updater can handle the given file.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if the file has a .yaml or .yml extension.
        """
        return file_path.suffix.lower() in {".yaml", ".yml"}

    async def async_update(
        self,
        file_path: Path,
        old_entity_id: str,
        new_entity_id: str,
        *,
        dry_run: bool = False,
    ) -> UpdateResult:
        """Update entity references in a YAML file.

        Uses text-based replacement to preserve comments and formatting.

        Args:
            file_path: Path to the YAML file to update.
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

            if not content.strip():
                # Empty file
                return UpdateResult(
                    success=True,
                    file_path=file_path,
                    changes_made=0,
                )

            # Perform text-based replacement
            new_content, changes_made = self._replace_entity_id(
                content, old_entity_id, new_entity_id
            )

            if changes_made == 0:
                return UpdateResult(
                    success=True,
                    file_path=file_path,
                    changes_made=0,
                )

            # Validate the new content is still valid YAML
            try:
                yaml_util.parse_yaml(new_content)
            except Exception as err:  # noqa: BLE001
                _LOGGER.error(
                    "Replacement produced invalid YAML in %s: %s",
                    file_path,
                    err,
                )
                return UpdateResult(
                    success=False,
                    file_path=file_path,
                    changes_made=0,
                    error=f"Replacement produced invalid YAML: {err}",
                )

            if not dry_run:
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

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to update %s: %s", file_path, err)
            return UpdateResult(
                success=False,
                file_path=file_path,
                changes_made=0,
                error=str(err),
            )

    def _replace_entity_id(
        self,
        content: str,
        old_entity_id: str,
        new_entity_id: str,
    ) -> tuple[str, int]:
        """Replace entity ID in YAML content using text-based replacement.

        This approach preserves comments and formatting by working directly
        with the text content rather than parsing and re-serializing.

        Args:
            content: The YAML file content.
            old_entity_id: The entity ID to replace.
            new_entity_id: The new entity ID.

        Returns:
            Tuple of (new content, number of replacements).
        """
        if old_entity_id not in content:
            return content, 0

        # Use word boundary matching to avoid partial replacements
        # Entity IDs are domain.object_id format
        # We need to be careful to only replace complete entity IDs
        # The pattern matches entity_id at word boundaries
        # \b doesn't work well with dots, so we use lookahead/lookbehind
        # Pattern: entity_id that is not part of a longer word
        pattern = re.compile(
            r"(?<![a-zA-Z0-9_.])"  # Not preceded by word char or dot
            + re.escape(old_entity_id)
            + r"(?![a-zA-Z0-9_])"  # Not followed by word char (dot is ok for end)
        )

        new_content, count = pattern.subn(new_entity_id, content)

        return new_content, count
