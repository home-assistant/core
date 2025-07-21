"""The nederlandse_spoorwegen component."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import NSAPIAuthError, NSAPIConnectionError, NSAPIError, NSAPIWrapper
from .const import CONF_FROM, CONF_ROUTES, CONF_TIME, CONF_TO, CONF_VIA, DOMAIN
from .coordinator import NSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Schema for a single route
ROUTE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_FROM): cv.string,
        vol.Required(CONF_TO): cv.string,
        vol.Optional(CONF_VIA): cv.string,
        vol.Optional(CONF_TIME): cv.string,
    }
)

# Schema for the integration configuration
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_ROUTES, default=[]): vol.All(
                    cv.ensure_list, [ROUTE_SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


# Define runtime data structure for this integration
@dataclass
class NSRuntimeData:
    """Runtime data for the Nederlandse Spoorwegen integration."""

    coordinator: NSDataUpdateCoordinator
    stations: list[Any] | None = None  # Full station objects with code and names
    stations_updated: str | None = None


type NSConfigEntry = ConfigEntry[NSRuntimeData]

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Nederlandse Spoorwegen component."""
    # Check if there's YAML configuration to import
    if DOMAIN in config:
        # Create import flow using the standard pattern
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "import"},
                data=config[DOMAIN],
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Set up Nederlandse Spoorwegen from a config entry."""
    api_key = entry.data[CONF_API_KEY]

    api_wrapper = NSAPIWrapper(hass, api_key)

    coordinator = NSDataUpdateCoordinator(hass, api_wrapper, entry)

    entry.runtime_data = NSRuntimeData(coordinator=coordinator)

    # Handle legacy routes migration (even if no routes exist)
    if not entry.options.get("routes_migrated", False):
        await _async_migrate_legacy_routes(hass, entry)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await coordinator.async_config_entry_first_refresh()

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
    if entry.options.get("routes_migrated", False):
        return

    legacy_routes = entry.data.get(CONF_ROUTES, [])

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "routes_migrated": True}
    )

    if not legacy_routes:
        return

    # Create API wrapper instance for station name normalization
    api_wrapper = NSAPIWrapper(hass, entry.data[CONF_API_KEY])

    # Fetch stations for name-to-code conversion
    try:
        stations = await api_wrapper.get_stations()
    except (NSAPIAuthError, NSAPIConnectionError, NSAPIError) as ex:
        _LOGGER.warning("Failed to fetch stations for migration: %s", ex)
        stations = []

    migrated_count = 0

    for route in legacy_routes:
        try:
            if not all(key in route for key in (CONF_NAME, CONF_FROM, CONF_TO)):
                _LOGGER.warning(
                    "Skipping invalid route missing required fields: %s", route
                )
                continue

            # Convert station names to codes using the API wrapper method
            from_station = str(
                api_wrapper.convert_station_name_to_code(route[CONF_FROM], stations)
            )
            to_station = str(
                api_wrapper.convert_station_name_to_code(route[CONF_TO], stations)
            )

            # Create subentry data with converted station codes
            subentry_data = {
                CONF_NAME: route[CONF_NAME],
                CONF_FROM: from_station,
                CONF_TO: to_station,
            }

            # Add optional fields if present
            if route.get(CONF_VIA):
                via_station = str(
                    api_wrapper.convert_station_name_to_code(route[CONF_VIA], stations)
                )
                subentry_data[CONF_VIA] = via_station

            if route.get(CONF_TIME):
                subentry_data[CONF_TIME] = route[CONF_TIME]

            # Create unique_id with converted station codes
            unique_id_parts = [
                from_station,
                to_station,
                subentry_data.get(CONF_VIA, ""),
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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        new_data = {**config_entry.data}

        if config_entry.minor_version < 1:
            # Future migrations can be added here for schema changes
            pass

        # Update the config entry with new data and version
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            minor_version=1,
            version=1,
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True
