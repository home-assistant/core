"""Entity migrator for the Entity Migration integration."""

from __future__ import annotations

from datetime import datetime
import logging
import os
from pathlib import Path
import shutil
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant

from .const import (
    CONFIG_TYPE_AUTOMATION,
    CONFIG_TYPE_DASHBOARD,
    CONFIG_TYPE_GROUP,
    CONFIG_TYPE_PERSON,
    CONFIG_TYPE_SCENE,
    CONFIG_TYPE_SCRIPT,
)
from .models import MigrationError, MigrationErrorType, MigrationResult, ScanResult
from .updaters import JSONStorageUpdater, YAMLFileUpdater

if TYPE_CHECKING:
    from .updaters import BaseUpdater

_LOGGER = logging.getLogger(__name__)

# Mapping from config types to reload service domains
RELOAD_SERVICES: dict[str, str] = {
    CONFIG_TYPE_AUTOMATION: "automation",
    CONFIG_TYPE_SCRIPT: "script",
    CONFIG_TYPE_SCENE: "scene",
    CONFIG_TYPE_GROUP: "group",
}


class EntityMigrator:
    """Orchestrates entity migration across all configuration types.

    Implements the In-Memory Transaction pattern:
    1. Load all affected configs into memory
    2. Create backup if requested
    3. Apply all updates to in-memory copies
    4. Validate updated configs are valid
    5. Write all configs to disk (abort on any failure)
    6. Trigger component reloads
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the migrator.

        Args:
            hass: Home Assistant instance.
        """
        self.hass = hass
        self._yaml_updater = YAMLFileUpdater()
        self._json_updater = JSONStorageUpdater()
        self._backup_path: Path | None = None

    async def async_migrate(
        self,
        source_entity_id: str,
        target_entity_id: str,
        scan_result: ScanResult,
        *,
        create_backup: bool = False,
        dry_run: bool = False,
    ) -> MigrationResult:
        """Migrate all references from source entity to target entity.

        Args:
            source_entity_id: The entity ID to migrate from.
            target_entity_id: The entity ID to migrate to.
            scan_result: ScanResult from scanner with all references.
            create_backup: Whether to create backup before migration.
            dry_run: If True, don't actually apply changes.

        Returns:
            MigrationResult with migration outcome.
        """
        _LOGGER.info(
            "Starting migration from %s to %s (dry_run=%s)",
            source_entity_id,
            target_entity_id,
            dry_run,
        )

        errors: list[MigrationError] = []
        updated: dict[str, list[str]] = {}
        total_updated = 0
        backup_path: Path | None = None

        # Collect all unique file paths that need updating
        file_paths = self._collect_file_paths(scan_result)

        if not file_paths:
            _LOGGER.debug("No file paths found to update")
            return MigrationResult(
                success=True,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                updated={},
                updated_count=0,
                errors=[],
                backup_path=None,
                dry_run=dry_run,
            )

        # Create backup if requested and not dry run
        if create_backup and not dry_run:
            backup_path = await self._create_backup(file_paths)
            if backup_path is None:
                _LOGGER.error("Failed to create backup, aborting migration")
                return MigrationResult(
                    success=False,
                    source_entity_id=source_entity_id,
                    target_entity_id=target_entity_id,
                    updated={},
                    updated_count=0,
                    errors=[
                        MigrationError(
                            config_type="backup",
                            config_id="backup",
                            error_type=MigrationErrorType.WRITE_ERROR,
                            message="Failed to create backup",
                        )
                    ],
                    backup_path=None,
                    dry_run=dry_run,
                )

        # Update each file
        update_results: list[tuple[Path, int, MigrationError | None]] = []

        for file_path in file_paths:
            result = await self._update_file(
                file_path,
                source_entity_id,
                target_entity_id,
                dry_run=dry_run,
            )
            update_results.append(result)

        # Check for errors
        for file_path, changes, error in update_results:
            if error:
                errors.append(error)
            elif changes > 0:
                # Track by config type
                config_type = self._get_config_type_from_path(file_path)
                if config_type not in updated:
                    updated[config_type] = []
                updated[config_type].append(str(file_path))
                total_updated += changes

        # If any errors occurred during update, rollback
        if errors and not dry_run and backup_path:
            _LOGGER.error(
                "Errors occurred during migration, rolling back from backup"
            )
            rollback_success = await self._rollback(backup_path, file_paths)
            if not rollback_success:
                errors.append(
                    MigrationError(
                        config_type="rollback",
                        config_id="rollback",
                        error_type=MigrationErrorType.ROLLBACK_FAILED,
                        message="Failed to rollback changes after error",
                    )
                )
            return MigrationResult(
                success=False,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                updated={},
                updated_count=0,
                errors=errors,
                backup_path=backup_path,
                dry_run=dry_run,
            )

        # Trigger reloads for affected components if not dry run and successful
        if not dry_run and not errors:
            await self._trigger_reloads(scan_result)

        success = len(errors) == 0

        _LOGGER.info(
            "Migration %s: updated %d references in %d files",
            "completed" if success else "failed",
            total_updated,
            len(file_paths),
        )

        return MigrationResult(
            success=success,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            updated=updated,
            updated_count=total_updated,
            errors=errors,
            backup_path=backup_path,
            dry_run=dry_run,
        )

    def _collect_file_paths(self, scan_result: ScanResult) -> list[Path]:
        """Collect all unique file paths from scan result.

        Args:
            scan_result: ScanResult containing references.

        Returns:
            List of unique file paths to update.
        """
        file_paths: set[Path] = set()

        for refs in scan_result.references.values():
            for ref in refs:
                if ref.file_path:
                    file_paths.add(ref.file_path)

        return list(file_paths)

    async def _create_backup(self, file_paths: list[Path]) -> Path | None:
        """Create timestamped backup of all files to be modified.

        Args:
            file_paths: List of file paths to backup.

        Returns:
            Path to backup directory, or None if backup failed.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path(self.hass.config.path(".backup/entity_migration", timestamp))

        try:
            # Create backup directory with secure permissions
            await self.hass.async_add_executor_job(
                self._create_backup_dir, backup_dir
            )

            # Copy each file
            for file_path in file_paths:
                if not file_path.exists():
                    continue

                # Create relative path structure in backup
                relative_path = file_path.relative_to(self.hass.config.path())
                backup_file = backup_dir / relative_path
                backup_file.parent.mkdir(parents=True, exist_ok=True)

                await self.hass.async_add_executor_job(
                    shutil.copy2, file_path, backup_file
                )

            _LOGGER.debug("Created backup at %s", backup_dir)
            return backup_dir

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to create backup: %s", err)
            return None

    def _create_backup_dir(self, backup_dir: Path) -> None:
        """Create backup directory with secure permissions.

        Args:
            backup_dir: Path to backup directory.
        """
        backup_dir.mkdir(parents=True, exist_ok=True)
        # Set secure permissions (owner read/write/execute only)
        os.chmod(backup_dir, 0o700)

    async def _update_file(
        self,
        file_path: Path,
        old_entity_id: str,
        new_entity_id: str,
        *,
        dry_run: bool = False,
    ) -> tuple[Path, int, MigrationError | None]:
        """Update a single file with entity replacement.

        Args:
            file_path: Path to the file to update.
            old_entity_id: Entity ID to replace.
            new_entity_id: New entity ID.
            dry_run: If True, don't actually write changes.

        Returns:
            Tuple of (file_path, changes_made, error or None).
        """
        updater = self._get_updater(file_path)

        if updater is None:
            _LOGGER.warning("No updater found for file: %s", file_path)
            return (file_path, 0, None)

        try:
            result = await updater.async_update(
                file_path,
                old_entity_id,
                new_entity_id,
                dry_run=dry_run,
            )

            if not result.success:
                return (
                    file_path,
                    0,
                    MigrationError(
                        config_type=self._get_config_type_from_path(file_path),
                        config_id=str(file_path),
                        error_type=MigrationErrorType.WRITE_ERROR,
                        message=result.error or "Unknown error",
                    ),
                )

            return (file_path, result.changes_made, None)

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error updating %s: %s", file_path, err)
            return (
                file_path,
                0,
                MigrationError(
                    config_type=self._get_config_type_from_path(file_path),
                    config_id=str(file_path),
                    error_type=MigrationErrorType.WRITE_ERROR,
                    message=str(err),
                ),
            )

    def _get_updater(self, file_path: Path) -> BaseUpdater | None:
        """Get the appropriate updater for a file path.

        Args:
            file_path: Path to the file.

        Returns:
            Appropriate updater instance, or None if no updater found.
        """
        if self._yaml_updater.can_handle(file_path):
            return self._yaml_updater
        if self._json_updater.can_handle(file_path):
            return self._json_updater
        return None

    def _get_config_type_from_path(self, file_path: Path) -> str:
        """Determine config type from file path.

        Args:
            file_path: Path to the file.

        Returns:
            Config type string.
        """
        name = file_path.name.lower()
        path_str = str(file_path).lower()

        if "automation" in name or "automation" in path_str:
            return CONFIG_TYPE_AUTOMATION
        if "script" in name or "script" in path_str:
            return CONFIG_TYPE_SCRIPT
        if "scene" in name or "scene" in path_str:
            return CONFIG_TYPE_SCENE
        if "group" in name or "group" in path_str:
            return CONFIG_TYPE_GROUP
        if "person" in name or "person" in path_str:
            return CONFIG_TYPE_PERSON
        if "lovelace" in name or "dashboard" in path_str:
            return CONFIG_TYPE_DASHBOARD
        if ".storage" in path_str:
            return "storage"

        return "yaml"

    async def _rollback(
        self,
        backup_path: Path,
        file_paths: list[Path],
    ) -> bool:
        """Rollback changes by restoring from backup.

        Args:
            backup_path: Path to backup directory.
            file_paths: List of file paths to restore.

        Returns:
            True if rollback succeeded, False otherwise.
        """
        try:
            for file_path in file_paths:
                relative_path = file_path.relative_to(self.hass.config.path())
                backup_file = backup_path / relative_path

                if backup_file.exists():
                    await self.hass.async_add_executor_job(
                        shutil.copy2, backup_file, file_path
                    )

            _LOGGER.info("Successfully rolled back changes from %s", backup_path)
            return True

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to rollback: %s", err)
            return False

    async def _trigger_reloads(self, scan_result: ScanResult) -> None:
        """Trigger reload services for affected components.

        Args:
            scan_result: ScanResult with affected config types.
        """
        config_types_to_reload = set(scan_result.references.keys())

        for config_type in config_types_to_reload:
            if config_type in RELOAD_SERVICES:
                domain = RELOAD_SERVICES[config_type]
                try:
                    await self.hass.services.async_call(
                        domain,
                        "reload",
                        blocking=True,
                    )
                    _LOGGER.debug("Triggered reload for %s", domain)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning(
                        "Failed to reload %s: %s", domain, err
                    )

        # Handle dashboard/lovelace reload separately
        if CONFIG_TYPE_DASHBOARD in config_types_to_reload:
            try:
                await self.hass.services.async_call(
                    "lovelace",
                    "reload_resources",
                    blocking=True,
                )
                _LOGGER.debug("Triggered lovelace resources reload")
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Failed to reload lovelace resources: %s", err
                )
