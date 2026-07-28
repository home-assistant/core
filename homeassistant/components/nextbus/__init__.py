"""NextBus platform."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util.hass_dict import HassKey

from .const import CONF_AGENCY, CONF_ROUTE, DOMAIN
from .coordinator import NextBusDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

type NextBusConfigEntry = ConfigEntry[NextBusDataUpdateCoordinator]

# Coordinators are shared between entries with the same agency and stop; the
# synchronous check and store below must stay free of awaits so concurrent
# entry setups cannot create duplicates.
NEXTBUS_KEY: HassKey[dict[str, NextBusDataUpdateCoordinator]] = HassKey(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: NextBusConfigEntry) -> bool:
    """Set up platforms for NextBus."""
    entry_agency = entry.data[CONF_AGENCY]
    entry_stop = entry.data[CONF_STOP]
    coordinator_key = f"{entry_agency}-{entry_stop}"

    coordinators = hass.data.setdefault(NEXTBUS_KEY, {})
    coordinator = coordinators.get(coordinator_key)
    if coordinator is None:
        coordinator = NextBusDataUpdateCoordinator(hass, entry_agency)
        coordinators[coordinator_key] = coordinator
    entry.runtime_data = coordinator

    coordinator.add_stop_route(entry_stop, entry.data[CONF_ROUTE])

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady from coordinator.last_exception

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NextBusConfigEntry) -> bool:
    """Unload a config entry."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_agency = entry.data[CONF_AGENCY]
        entry_stop = entry.data[CONF_STOP]
        coordinator = entry.runtime_data
        coordinator.remove_stop_route(entry_stop, entry.data[CONF_ROUTE])

        if not coordinator.has_routes():
            await coordinator.async_shutdown()
            hass.data[NEXTBUS_KEY].pop(f"{entry_agency}-{entry_stop}")

        return True

    return False
