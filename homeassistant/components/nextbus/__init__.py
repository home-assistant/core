"""NextBus platform."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_STOP, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_AGENCY, CONF_ROUTE, DOMAIN
from .coordinator import NextBusDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platforms for NextBus."""
    entry_agency = entry.data[CONF_AGENCY]

    coordinator: NextBusDataUpdateCoordinator = hass.data.setdefault(DOMAIN, {}).get(
        entry_agency
    )
    if coordinator is None:
        coordinator = NextBusDataUpdateCoordinator(hass, entry_agency)
        hass.data[DOMAIN][entry_agency] = coordinator

    coordinator.add_stop_route(entry.data[CONF_STOP], entry.data[CONF_ROUTE])

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_agency = entry.data.get(CONF_AGENCY)
        coordinator: NextBusDataUpdateCoordinator = hass.data[DOMAIN][entry_agency]
        coordinator.remove_stop_route(entry.data[CONF_STOP], entry.data[CONF_ROUTE])
        if not coordinator.has_routes():
            hass.data[DOMAIN].pop(entry_agency)

        return True

    return False
