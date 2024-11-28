"""The OpenStreetMap integration."""

from __future__ import annotations

import voluptuous as vol

# from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import _LOGGER, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .search import (
    get_address_coordinates,
    get_Coordinates,
    # AddressSearchView,
    search_address,  # imports search function from search.py
)

# TODO List the platforms that you want to support. # pylint: disable=fixme
# For your initial PR, limit it to 1 platform.
# PLATFORMS: list[Platform] = [Platform.LIGHT]
PLATFORMS: list[Platform] = []

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# TODO Create ConfigEntry type alias with API object
# TODO Rename type alias and update all entry annotations
# type OpenStreetMapConfigEntry = ConfigEntry[MyApi]  # noqa: F821


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OpenStreetMap integration."""
    # Initialize the domain-specific data
    hass.data[DOMAIN] = {}

    # Optionally, set a state or initialize any service here
    hass.states.async_set(f"{DOMAIN}.integration", "loaded")

    # Register the search service
    hass.services.async_register(
        DOMAIN,
        "search",
        async_handle_search,
        schema=vol.Schema({vol.Required("query"): str}),
    )

    # Register the get_coordinates service. Not sure if this is needed
    hass.services.async_register(
        DOMAIN,
        "get_coordinates",
        async_handle_get_coordinates,
        schema=cv.make_entity_service_schema({vol.Required("json_data"): cv.Any}),
    )

    # Register the get_address_coordinates service
    hass.services.async_register(
        DOMAIN,
        "get_address_coordinates",
        async_handle_get_address_coordinates,
        schema=vol.Schema({vol.Required("query"): str}),
        # schema=cv.make_entity_service_schema({vol.Required("query"): str}),
    )

    return True


# TODO uncomment this code and fix the todos. Note! Need to uncomment the imports as well
# # TODO Update entry annotation
# async def async_setup_entry(
#     hass: HomeAssistant, entry: OpenStreetMapConfigEntry
# ) -> bool:
#     """Set up OpenStreetMap from a config entry."""

#     # TODO 1. Create API instance
#     # TODO 2. Validate the API connection (and authentication)
#     # TODO 3. Store an API object for your platforms to access
#     # entry.runtime_data = MyAPI(...)

#     await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

#     return True


# # TODO Update entry annotation
# async def async_unload_entry(
#     hass: HomeAssistant, entry: OpenStreetMapConfigEntry
# ) -> bool:
#     """Unload a config entry."""
#     return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_handle_search(hass: HomeAssistant, call: ServiceCall) -> dict[str, str]:
    """Handle a service call to search for an address or coordinates with OpenStreetMap.

    Fetches results based on the query from the service call and updates the last search state in Home Assistant.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        call (ServiceCall): The service call object containing the data payload.

    Returns:
        dict[str, str]: A dictionary containing the search results if successful, or an error message.

    """
    query = call.data.get("query", "")
    if not query:
        error_message = {"error": "Query is missing or empty"}
        hass.states.async_set(
            f"{DOMAIN}.last_search", f"Error: {error_message['error']}"
        )
        return error_message

    results = search_address(query)

    # fire event with error or full result
    if "error" in results:
        hass.states.async_set(f"{DOMAIN}.last_search", f"Error: {results['error']}")
        hass.bus.async_fire(f"{DOMAIN}_event", {"error": results["error"]})
    else:
        hass.bus.async_fire(f"{DOMAIN}_event",
                            {"type": "search",
                             "query": query,
                             "results": results
                             })

    return results


# right now, this can't be called from frontend since it does not fire any events
async def async_handle_get_coordinates(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, str]:
    """Handle the service call for extracting coordinates from JSON.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        call (ServiceCall): The service call object containing the data payload.

    Returns:
        dict[str, str]: A dictionary containing the search results if json_data, or an error message.

    """
    json_data = call.data.get("json_data")
    if not json_data:
        _LOGGER.error("No JSON data provided")
        return {"error": "No JSON data provided"}

    return get_Coordinates(json_data)


# Service handler for getting coordinates from an address
async def async_handle_get_address_coordinates(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, str]:
    """Handle the service call to get coordinates from an address query.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        call (ServiceCall): The service call object containing the data payload.

    Returns:
        dict[str, str]: A dictionary containing the search results if json_data, or an error message.

    """
    query = call.data.get("query")
    if not query:
        _LOGGER.error("No query provided")
        return {"error": "No query provided"}

    coordinates = get_address_coordinates(query)

    # Fire event with error or coordinates
    if "error" in coordinates:
        _LOGGER.error(f"Error fetching coordinates: {coordinates['error']}")
        hass.bus.async_fire(f"{DOMAIN}_event", {"error": coordinates["error"]})
    else:
        hass.bus.async_fire(f"{DOMAIN}_event",
                            {"type": "get_coordinates",
                             "query": query,
                             "coordinates": coordinates
                            })

    return coordinates
