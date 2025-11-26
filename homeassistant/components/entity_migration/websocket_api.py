"""WebSocket API for the Entity Migration integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback, valid_entity_id

from .migrator import EntityMigrator
from .scanner import EntityMigrationScanner
from .validators import async_validate_compatibility

if TYPE_CHECKING:
    from .models import CompatibilityResult, MigrationResult, ScanResult


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the entity migration WebSocket API."""
    websocket_api.async_register_command(hass, websocket_scan)
    websocket_api.async_register_command(hass, websocket_validate)
    websocket_api.async_register_command(hass, websocket_migrate)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "entity_migration/scan",
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def websocket_scan(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle entity_migration/scan WebSocket command.

    Scans for all references to the specified entity across configurations.
    """
    entity_id = msg["entity_id"]

    # Validate entity_id format
    if not valid_entity_id(entity_id):
        connection.send_error(
            msg["id"],
            "invalid_entity_id",
            f"Invalid entity ID format: {entity_id}",
        )
        return

    scanner = EntityMigrationScanner(hass)

    # Scanner internally handles all scan errors gracefully,
    # so no exception catching needed here
    result: ScanResult = await scanner.async_scan(entity_id)

    connection.send_result(msg["id"], result.as_dict())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "entity_migration/validate",
        vol.Required("source_entity_id"): str,
        vol.Required("target_entity_id"): str,
    }
)
@websocket_api.async_response
async def websocket_validate(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle entity_migration/validate WebSocket command.

    Validates compatibility between source and target entities for migration.
    Returns warnings for potential issues (domain mismatch, device class mismatch,
    unit mismatch) and blocking errors (target not found).
    """
    source_entity_id = msg["source_entity_id"]
    target_entity_id = msg["target_entity_id"]

    # Validate entity ID formats
    if not valid_entity_id(source_entity_id):
        connection.send_error(
            msg["id"],
            "invalid_entity_id",
            f"Invalid source entity ID format: {source_entity_id}",
        )
        return

    if not valid_entity_id(target_entity_id):
        connection.send_error(
            msg["id"],
            "invalid_entity_id",
            f"Invalid target entity ID format: {target_entity_id}",
        )
        return

    result: CompatibilityResult = await async_validate_compatibility(
        hass, source_entity_id, target_entity_id
    )

    connection.send_result(msg["id"], result.as_dict())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "entity_migration/migrate",
        vol.Required("source_entity_id"): str,
        vol.Required("target_entity_id"): str,
        vol.Optional("dry_run", default=False): bool,
        vol.Optional("create_backup", default=False): bool,
        vol.Optional("force", default=False): bool,
    }
)
@websocket_api.async_response
async def websocket_migrate(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle entity_migration/migrate WebSocket command.

    Migrates all references from source entity to target entity.
    Supports dry_run mode to preview changes without applying them.
    Can create backup before migration if requested.
    Use force=true to bypass compatibility warnings.
    """
    source_entity_id = msg["source_entity_id"]
    target_entity_id = msg["target_entity_id"]
    dry_run = msg["dry_run"]
    create_backup = msg["create_backup"]
    force = msg["force"]

    # Validate entity ID formats
    if not valid_entity_id(source_entity_id):
        connection.send_error(
            msg["id"],
            "invalid_entity_id",
            f"Invalid source entity ID format: {source_entity_id}",
        )
        return

    if not valid_entity_id(target_entity_id):
        connection.send_error(
            msg["id"],
            "invalid_entity_id",
            f"Invalid target entity ID format: {target_entity_id}",
        )
        return

    # Validate compatibility unless force is True
    if not force:
        validation_result = await async_validate_compatibility(
            hass, source_entity_id, target_entity_id
        )

        if not validation_result.valid:
            # Build detailed error message from blocking errors
            error_messages = [e.message for e in validation_result.blocking_errors]
            connection.send_error(
                msg["id"],
                "validation_failed",
                f"Migration blocked: {'; '.join(error_messages)}",
            )
            return

    # Scan for references
    scanner = EntityMigrationScanner(hass)
    scan_result: ScanResult = await scanner.async_scan(source_entity_id)

    if scan_result.total_count == 0:
        # No references found, return success with no changes
        connection.send_result(
            msg["id"],
            {
                "success": True,
                "source_entity_id": source_entity_id,
                "target_entity_id": target_entity_id,
                "updated": {},
                "updated_count": 0,
                "errors": [],
                "backup_path": None,
                "dry_run": dry_run,
            },
        )
        return

    # Perform migration
    migrator = EntityMigrator(hass)
    result: MigrationResult = await migrator.async_migrate(
        source_entity_id,
        target_entity_id,
        scan_result,
        create_backup=create_backup,
        dry_run=dry_run,
    )

    connection.send_result(msg["id"], result.as_dict())
