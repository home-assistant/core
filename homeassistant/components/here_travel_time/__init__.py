"""The HERE Travel Time integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_MODE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from .const import (
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION_ENTITY_ID,
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_ORIGIN_ENTITY_ID,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
    CONF_ROUTE_MODE,
    DOMAIN,
    TRAVEL_MODE_PUBLIC,
)
from .coordinator import (
    HERERoutingDataUpdateCoordinator,
    HERETransitDataUpdateCoordinator,
)
from .model import HERETravelTimeConfig

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up HERE Travel Time from a config entry."""
    api_key = config_entry.data[CONF_API_KEY]

    arrival = dt.parse_time(config_entry.options.get(CONF_ARRIVAL_TIME, ""))
    departure = dt.parse_time(config_entry.options.get(CONF_DEPARTURE_TIME, ""))

    here_travel_time_config = HERETravelTimeConfig(
        destination_latitude=config_entry.data.get(CONF_DESTINATION_LATITUDE),
        destination_longitude=config_entry.data.get(CONF_DESTINATION_LONGITUDE),
        destination_entity_id=config_entry.data.get(CONF_DESTINATION_ENTITY_ID),
        origin_latitude=config_entry.data.get(CONF_ORIGIN_LATITUDE),
        origin_longitude=config_entry.data.get(CONF_ORIGIN_LONGITUDE),
        origin_entity_id=config_entry.data.get(CONF_ORIGIN_ENTITY_ID),
        travel_mode=config_entry.data[CONF_MODE],
        route_mode=config_entry.options[CONF_ROUTE_MODE],
        arrival=arrival,
        departure=departure,
    )

    if config_entry.data[CONF_MODE] in {TRAVEL_MODE_PUBLIC, "publicTransportTimeTable"}:
        hass.data.setdefault(DOMAIN, {})[
            config_entry.entry_id
        ] = HERETransitDataUpdateCoordinator(
            hass,
            api_key,
            here_travel_time_config,
        )
    else:
        hass.data.setdefault(DOMAIN, {})[
            config_entry.entry_id
        ] = HERERoutingDataUpdateCoordinator(
            hass,
            api_key,
            here_travel_time_config,
        )
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
