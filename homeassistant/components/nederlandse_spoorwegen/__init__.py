"""The nederlandse_spoorwegen component."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from types import MappingProxyType
from typing import Any

from ns_api import NSAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_FROM, CONF_ROUTES, CONF_TIME, CONF_TO, CONF_VIA, DOMAIN
from .coordinator import NSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# This integration can only be configured via config entries
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


# Define runtime data structure for this integration
@dataclass
class NSRuntimeData:
    """Runtime data for the Nederlandse Spoorwegen integration."""

    coordinator: NSDataUpdateCoordinator
    stations: list[Any] | None = None  # Full station objects with code and names
    stations_updated: str | None = None


type NSConfigEntry = ConfigEntry[NSRuntimeData]

PLATFORMS = [Platform.SENSOR]

# Service schemas
ADD_ROUTE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_FROM): str,
        vol.Required(CONF_TO): str,
        vol.Optional(CONF_VIA): str,
        vol.Optional(CONF_TIME): str,
    }
)
REMOVE_ROUTE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Nederlandse Spoorwegen component."""

    async def async_add_route(call: ServiceCall) -> None:
        """Add a new route."""
        # Find the NS integration config entry
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError("No Nederlandse Spoorwegen integration found")

        entry = entries[0]  # Assume single integration
        if entry.state.name != "LOADED":
            raise ServiceValidationError(
                "Nederlandse Spoorwegen integration not loaded"
            )

        coordinator = entry.runtime_data.coordinator

        # Create route dict from service call data
        route = {
            CONF_NAME: call.data[CONF_NAME],
            CONF_FROM: call.data[CONF_FROM].upper(),
            CONF_TO: call.data[CONF_TO].upper(),
        }
        if call.data.get(CONF_VIA):
            route[CONF_VIA] = call.data[CONF_VIA].upper()

        if call.data.get(CONF_TIME):
            route[CONF_TIME] = call.data[CONF_TIME]

        # Add route via coordinator
        await coordinator.async_add_route(route)

    async def async_remove_route(call: ServiceCall) -> None:
        """Remove a route."""
        # Find the NS integration config entry
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError("No Nederlandse Spoorwegen integration found")

        entry = entries[0]  # Assume single integration
        if entry.state.name != "LOADED":
            raise ServiceValidationError(
                "Nederlandse Spoorwegen integration not loaded"
            )

        coordinator = entry.runtime_data.coordinator

        # Remove route via coordinator
        await coordinator.async_remove_route(call.data[CONF_NAME])

    # Register services
    hass.services.async_register(
        DOMAIN, "add_route", async_add_route, schema=ADD_ROUTE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "remove_route", async_remove_route, schema=REMOVE_ROUTE_SCHEMA
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Set up Nederlandse Spoorwegen from a config entry."""
    # Set runtime_data for this entry (store the coordinator only)
    api_key = entry.data.get(CONF_API_KEY)
    client = NSAPI(api_key)

    # Create coordinator
    coordinator = NSDataUpdateCoordinator(hass, client, entry)

    # Initialize runtime data with coordinator
    entry.runtime_data = NSRuntimeData(coordinator=coordinator)

    # Migrate legacy routes on first setup if needed
    await _async_migrate_legacy_routes(hass, entry)

    # Add update listener after migration to avoid reload during migration
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Fetch initial data so we have data when entities subscribe
    try:
        await coordinator.async_config_entry_first_refresh()
    except asyncio.CancelledError:
        # Handle cancellation gracefully (e.g., during test shutdown)
        _LOGGER.debug("Coordinator first refresh was cancelled, continuing setup")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload NS integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_migrate_legacy_routes(
    hass: HomeAssistant, entry: NSConfigEntry
) -> None:
    """Migrate legacy routes from configuration data into subentries.

    This handles routes stored in entry.data[CONF_ROUTES] from legacy YAML config.
    One-time migration to avoid duplicate imports.
    """
    # Check if migration has already been performed
    if entry.options.get("routes_migrated", False):
        _LOGGER.debug("Routes already migrated for entry %s", entry.entry_id)
        return

    # Get legacy routes from data (from YAML configuration)
    legacy_routes = entry.data.get(CONF_ROUTES, [])

    # Mark migration as starting to prevent duplicate calls
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "routes_migrated": True}
    )

    if not legacy_routes:
        _LOGGER.debug(
            "No legacy routes found in configuration, migration marked as complete"
        )
        return

    _LOGGER.info(
        "Migrating %d legacy routes from configuration to subentries",
        len(legacy_routes),
    )
    migrated_count = 0

    for route in legacy_routes:
        try:
            # Validate required fields
            if not all(key in route for key in (CONF_NAME, CONF_FROM, CONF_TO)):
                _LOGGER.warning(
                    "Skipping invalid route missing required fields: %s", route
                )
                continue

            # Create subentry data
            subentry_data = {
                CONF_NAME: route[CONF_NAME],
                CONF_FROM: route[CONF_FROM].upper(),
                CONF_TO: route[CONF_TO].upper(),
            }

            # Add optional fields if present
            if route.get(CONF_VIA):
                subentry_data[CONF_VIA] = route[CONF_VIA].upper()

            if route.get(CONF_TIME):
                subentry_data[CONF_TIME] = route[CONF_TIME]

            # Create unique_id with uppercase station codes for consistency
            unique_id_parts = [
                route[CONF_FROM].upper(),
                route[CONF_TO].upper(),
                route.get(CONF_VIA, "").upper(),
            ]
            unique_id = "_".join(part for part in unique_id_parts if part)

            # Create the subentry
            subentry = ConfigSubentry(
                data=MappingProxyType(subentry_data),
                subentry_type="route",
                title=route[CONF_NAME],
                unique_id=unique_id,
            )

            # Add the subentry to the config entry
            hass.config_entries.async_add_subentry(entry, subentry)
            migrated_count += 1
            _LOGGER.debug("Successfully migrated route: %s", route[CONF_NAME])

        except (KeyError, ValueError) as ex:
            _LOGGER.warning(
                "Error migrating route %s: %s", route.get(CONF_NAME, "unknown"), ex
            )

    # Clean up legacy routes from data
    new_data = {**entry.data}
    if CONF_ROUTES in new_data:
        new_data.pop(CONF_ROUTES)

    # Update the config entry to remove legacy routes
    hass.config_entries.async_update_entry(entry, data=new_data)

    _LOGGER.info(
        "Migration complete: %d of %d routes successfully migrated to subentries",
        migrated_count,
        len(legacy_routes),
    )
