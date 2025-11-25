"""Data models for the Entity Migration integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class WarningType(StrEnum):
    """Types of compatibility warnings."""

    DOMAIN_MISMATCH = "domain_mismatch"
    DEVICE_CLASS_MISMATCH = "device_class_mismatch"
    UNIT_MISMATCH = "unit_mismatch"


class ErrorType(StrEnum):
    """Types of compatibility errors."""

    TARGET_NOT_FOUND = "target_not_found"
    SOURCE_NOT_FOUND = "source_not_found"
    INVALID_ENTITY_ID = "invalid_entity_id"


class MigrationErrorType(StrEnum):
    """Types of migration errors."""

    PARSE_ERROR = "parse_error"
    WRITE_ERROR = "write_error"
    VALIDATION_ERROR = "validation_error"
    ROLLBACK_FAILED = "rollback_failed"


@dataclass
class Reference:
    """A single reference to an entity in configuration."""

    config_type: str
    """Type of configuration: automation, script, dashboard, etc."""

    config_id: str
    """Unique identifier of the config item."""

    config_name: str
    """Human-readable name of the config item."""

    location: str
    """Where in the config the entity is referenced: trigger, action, etc."""

    file_path: Path | None = None
    """Path to the YAML file for YAML-based configs."""

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "config_type": self.config_type,
            "config_id": self.config_id,
            "config_name": self.config_name,
            "location": self.location,
            "file_path": str(self.file_path) if self.file_path else None,
        }


@dataclass
class ScanResult:
    """Result of scanning for entity references."""

    source_entity_id: str
    """The entity ID that was scanned for."""

    references: dict[str, list[Reference]] = field(default_factory=dict)
    """References grouped by config type."""

    total_count: int = 0
    """Total number of references found."""

    is_location_based: bool = False
    """Whether the source entity is location-based (for future Epic 3)."""

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_entity_id": self.source_entity_id,
            "references": {
                config_type: [ref.as_dict() for ref in refs]
                for config_type, refs in self.references.items()
            },
            "total_count": self.total_count,
            "is_location_based": self.is_location_based,
        }


@dataclass
class CompatibilityWarning:
    """A compatibility warning for entity migration."""

    warning_type: WarningType
    """Type of warning: domain_mismatch, device_class_mismatch, unit_mismatch."""

    message: str
    """User-friendly message explaining the warning."""

    source_value: str | None = None
    """Value from the source entity."""

    target_value: str | None = None
    """Value from the target entity."""

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "warning_type": self.warning_type,
            "message": self.message,
            "source_value": self.source_value,
            "target_value": self.target_value,
        }


@dataclass
class CompatibilityError:
    """A blocking compatibility error for entity migration."""

    error_type: ErrorType
    """Type of error: target_not_found, source_not_found, invalid_entity_id."""

    message: str
    """User-friendly message explaining the error."""

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error_type": self.error_type,
            "message": self.message,
        }


@dataclass
class CompatibilityResult:
    """Result of compatibility validation between source and target entities."""

    valid: bool
    """True if no blocking errors exist (migration can proceed with warnings)."""

    source_entity_id: str
    """The source entity ID that was validated."""

    target_entity_id: str
    """The target entity ID that was validated."""

    warnings: list[CompatibilityWarning] = field(default_factory=list)
    """List of non-blocking warnings."""

    blocking_errors: list[CompatibilityError] = field(default_factory=list)
    """List of blocking errors that prevent migration."""

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "valid": self.valid,
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "warnings": [w.as_dict() for w in self.warnings],
            "blocking_errors": [e.as_dict() for e in self.blocking_errors],
        }


@dataclass
class UpdateResult:
    """Result of updating a single configuration file."""

    success: bool
    """Whether the update was successful."""

    file_path: Path
    """Path to the updated file."""

    changes_made: int
    """Number of entity references replaced."""

    error: str | None = None
    """Error message if update failed."""

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "file_path": str(self.file_path),
            "changes_made": self.changes_made,
            "error": self.error,
        }


@dataclass
class MigrationError:
    """An error that occurred during migration."""

    config_type: str
    """Type of configuration that failed."""

    config_id: str
    """Identifier of the configuration that failed."""

    error_type: MigrationErrorType
    """Type of error: parse_error, write_error, validation_error."""

    message: str
    """Error message describing what went wrong."""

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "config_type": self.config_type,
            "config_id": self.config_id,
            "error_type": self.error_type,
            "message": self.message,
        }


@dataclass
class MigrationResult:
    """Result of an entity migration operation."""

    success: bool
    """Whether the migration completed successfully."""

    source_entity_id: str
    """The source entity ID that was migrated from."""

    target_entity_id: str
    """The target entity ID that was migrated to."""

    updated: dict[str, list[str]] = field(default_factory=dict)
    """Config types mapped to lists of updated config IDs."""

    updated_count: int = 0
    """Total number of references updated."""

    errors: list[MigrationError] = field(default_factory=list)
    """List of errors that occurred during migration."""

    backup_path: Path | None = None
    """Path to backup directory if backup was created."""

    dry_run: bool = False
    """Whether this was a dry run (no changes applied)."""

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "updated": self.updated,
            "updated_count": self.updated_count,
            "errors": [e.as_dict() for e in self.errors],
            "backup_path": str(self.backup_path) if self.backup_path else None,
            "dry_run": self.dry_run,
        }
