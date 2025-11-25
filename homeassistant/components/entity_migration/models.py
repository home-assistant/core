"""Data models for the Entity Migration integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
        """
        Return a dictionary representation of the Reference suitable for JSON serialization.
        
        The dictionary contains "config_type", "config_id", "config_name", "location", and "file_path" (a string when present, otherwise None).
        
        Returns:
            dict[str, Any]: Mapping of field names to JSON-serializable values.
        """
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
        """
        Produce a dictionary representation of the ScanResult suitable for JSON serialization.
        
        Returns:
            result (dict[str, Any]): Dictionary with keys:
                - `source_entity_id` (str): The scanned entity ID.
                - `references` (dict[str, list[dict[str, Any]]]): Mapping from config type to a list of Reference dictionaries produced by Reference.as_dict().
                - `total_count` (int): Total number of references found.
                - `is_location_based` (bool): Whether the source entity is location-based.
        """
        return {
            "source_entity_id": self.source_entity_id,
            "references": {
                config_type: [ref.as_dict() for ref in refs]
                for config_type, refs in self.references.items()
            },
            "total_count": self.total_count,
            "is_location_based": self.is_location_based,
        }