"""The Smart Meter B Route integration."""

import logging

from homeassistant.const import CONF_ID, Platform
from homeassistant.core import HomeAssistant

from .coordinator import BRouteConfigEntry, BRouteUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BRouteConfigEntry) -> bool:
    """Set up Smart Meter B Route from a config entry."""

    coordinator = BRouteUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if (
        route_b_id := coordinator.api.get_route_b_id().get("authentication id")
    ) != entry.data[CONF_ID]:
        _LOGGER.error(
            "Route B ID mismatch: expected %s but got %s",
            entry.data[CONF_ID],
            route_b_id,
        )
        return False

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BRouteConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.async_add_executor_job(entry.runtime_data.api.close)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
