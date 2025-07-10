"""The nederlandse_spoorwegen component."""

from __future__ import annotations

import logging
from typing import TypedDict

from ns_api import NSAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_FROM, CONF_TIME, CONF_TO, CONF_VIA, DOMAIN
from .coordinator import NSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# This integration can only be configured via config entries
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


# Define runtime data structure for this integration
class NSRuntimeData(TypedDict, total=False):
    """TypedDict for runtime data used by the Nederlandse Spoorwegen integration."""

    coordinator: NSDataUpdateCoordinator
    approved_station_codes: list[str]
    approved_station_codes_updated: str


class NSConfigEntry(ConfigEntry[NSRuntimeData]):
    """Config entry for the Nederlandse Spoorwegen integration."""


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

        coordinator = entry.runtime_data["coordinator"]

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

        coordinator = entry.runtime_data["coordinator"]

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
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Set runtime_data for this entry (store the coordinator only)
    api_key = entry.data.get(CONF_API_KEY)
    client = NSAPI(api_key)

    # Create coordinator
    coordinator = NSDataUpdateCoordinator(hass, client, entry)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = NSRuntimeData(
        coordinator=coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload NS integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
