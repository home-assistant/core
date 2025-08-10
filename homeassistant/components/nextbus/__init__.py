"""NextBus platform."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_AGENCY, CONF_ROUTE, DOMAIN
from .coordinator import NextBusDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platforms for NextBus."""
    entry_agency = entry.data[CONF_AGENCY]
    entry_stop = entry.data[CONF_STOP]
    coordinator_key = f"{entry_agency}-{entry_stop}"

    coordinator: NextBusDataUpdateCoordinator | None = hass.data.setdefault(
        DOMAIN, {}
    ).get(
        coordinator_key,
    )
    if coordinator is None:
        coordinator = NextBusDataUpdateCoordinator(hass, entry_agency)
        hass.data[DOMAIN][coordinator_key] = coordinator

    coordinator.add_stop_route(entry_stop, entry.data[CONF_ROUTE])

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady from coordinator.last_exception

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_agency = entry.data[CONF_AGENCY]
        entry_stop = entry.data[CONF_STOP]
        coordinator_key = f"{entry_agency}-{entry_stop}"

        coordinator: NextBusDataUpdateCoordinator = hass.data[DOMAIN][coordinator_key]
        coordinator.remove_stop_route(entry_stop, entry.data[CONF_ROUTE])

        if not coordinator.has_routes():
            await coordinator.async_shutdown()
            hass.data[DOMAIN].pop(coordinator_key)

        return True

    return False
