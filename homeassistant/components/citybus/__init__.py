"""CityBus platform."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_ROUTE, CONF_DIRECTION, CONF_STOP, DOMAIN
from .coordinator import CityBusDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platforms for CityBus."""
    entry_route = entry.data[CONF_ROUTE]
    entry_direction = entry.data[CONF_DIRECTION]
    entry_stop = entry.data[CONF_STOP]
    coordinator_key = f"{entry_route}-{entry_direction}-{entry_stop}"

    coordinator: CityBusDataUpdateCoordinator | None = hass.data.setdefault(
        DOMAIN, {}
    ).get(
        coordinator_key,
    )
    if coordinator is None:
        coordinator = CityBusDataUpdateCoordinator(hass)
        hass.data[DOMAIN][coordinator_key] = coordinator

    coordinator.add_route_stop(entry_route, entry_direction, entry_stop)

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady from coordinator.last_exception

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_route = entry.data[CONF_ROUTE]
        entry_direction = entry.data[CONF_DIRECTION]
        entry_stop = entry.data[CONF_STOP]
        coordinator_key = f"{entry_route}-{entry_direction}-{entry_stop}"

        coordinator: CityBusDataUpdateCoordinator = hass.data[DOMAIN][coordinator_key]
        coordinator.remove_route_stop(entry_route, entry_direction, entry_stop)

        if not coordinator.has_route_stops():
            await coordinator.async_shutdown()
            hass.data[DOMAIN].pop(coordinator_key)

        return True

    return False
