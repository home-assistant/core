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
    """
    Initialize the Entity Migration integration.
    
    Registers the integration's WebSocket API and a "scan" service that scans configurations for references to a given entity_id. The scan service raises ServiceValidationError (translation_domain=DOMAIN, translation_key="scan_failed") when scanning fails and returns the scan result as a dictionary.
    
    Returns:
        True when setup completed successfully.
    """
    _LOGGER.debug("Setting up Entity Migration integration")

    # Register WebSocket commands
    websocket_api.async_setup(hass)

    # Register services
    async def handle_scan(call: ServiceCall) -> ServiceResponse:
        """
        Process an entity migration scan service call and return the scan result as a dictionary.
        
        Parameters:
            call (ServiceCall): Service call containing the `entity_id` to scan (key: `ATTR_ENTITY_ID`).
        
        Returns:
            dict: Dictionary representation of the scan result.
        
        Raises:
            ServiceValidationError: If the scan fails; contains translation_domain `DOMAIN`, translation_key `scan_failed`, and a placeholder `error` with the failure message.
        """
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