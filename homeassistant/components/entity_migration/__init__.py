"""The Entity Migration integration.

This integration provides entity reference scanning capabilities for
Home Assistant, allowing users to discover all places where an entity
is referenced across automations, scripts, scenes, groups, dashboards,
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
from .scanner import EntityMigrationScanner

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

SERVICE_SCAN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Entity Migration integration."""
    _LOGGER.debug("Setting up Entity Migration integration")

    # Register WebSocket commands
    websocket_api.async_setup(hass)

    # Register services
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

    _LOGGER.debug("Entity Migration integration setup complete")
    return True
