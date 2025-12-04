"""The Entity Migration integration.

This integration provides entity reference scanning and migration capabilities
for Home Assistant, allowing users to discover and migrate all places where
an entity is referenced across automations, scripts, scenes, groups, dashboards,
and other configurations.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import ATTR_ENTITY_ID, DOMAIN
from .migrator import EntityMigrator
from .scanner import EntityMigrationScanner
from .validators import async_validate_compatibility

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

# Service attribute names
ATTR_SOURCE_ENTITY_ID = "source_entity_id"
ATTR_TARGET_ENTITY_ID = "target_entity_id"
ATTR_DRY_RUN = "dry_run"
ATTR_CREATE_BACKUP = "create_backup"
ATTR_FORCE = "force"

SERVICE_SCAN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    }
)

SERVICE_MIGRATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SOURCE_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_TARGET_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_DRY_RUN, default=False): cv.boolean,
        vol.Optional(ATTR_CREATE_BACKUP, default=False): cv.boolean,
        vol.Optional(ATTR_FORCE, default=False): cv.boolean,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Entity Migration integration."""
    _LOGGER.debug("Setting up Entity Migration integration")

    # Register WebSocket commands
    websocket_api.async_setup(hass)

    # Register scan service
    async def handle_scan(call: ServiceCall) -> ServiceResponse:
        """Handle the scan service call."""
        entity_id = call.data[ATTR_ENTITY_ID]

        scanner = EntityMigrationScanner(hass)

        try:
            result = await scanner.async_scan(entity_id)
        except Exception as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="scan_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        return result.as_dict()

    hass.services.async_register(
        DOMAIN,
        "scan",
        handle_scan,
        schema=SERVICE_SCAN_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    # Register migrate service
    async def handle_migrate(call: ServiceCall) -> ServiceResponse:
        """Handle the migrate service call."""
        source_entity_id = call.data[ATTR_SOURCE_ENTITY_ID]
        target_entity_id = call.data[ATTR_TARGET_ENTITY_ID]
        dry_run = call.data[ATTR_DRY_RUN]
        create_backup = call.data[ATTR_CREATE_BACKUP]
        force = call.data[ATTR_FORCE]

        # Validate compatibility unless force is True
        if not force:
            validation_result = await async_validate_compatibility(
                hass, source_entity_id, target_entity_id
            )

            if not validation_result.valid:
                errors = [e.message for e in validation_result.blocking_errors]
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="validation_failed",
                    translation_placeholders={"error": "; ".join(errors)},
                )

        # Scan for references
        scanner = EntityMigrationScanner(hass)
        try:
            scan_result = await scanner.async_scan(source_entity_id)
        except Exception as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="scan_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        # Perform migration
        migrator = EntityMigrator(hass)
        try:
            result = await migrator.async_migrate(
                source_entity_id,
                target_entity_id,
                scan_result,
                create_backup=create_backup,
                dry_run=dry_run,
            )
        except Exception as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="migration_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        return result.as_dict()

    hass.services.async_register(
        DOMAIN,
        "migrate",
        handle_migrate,
        schema=SERVICE_MIGRATE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    _LOGGER.debug("Entity Migration integration setup complete")
    return True
