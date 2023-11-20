"""The PubliBike Public API integration."""


from pypublibike.publibike import PubliBike

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import BATTERY_LIMIT, BATTERY_LIMIT_DEFAULT, DOMAIN, STATION_ID
from .coordinator import PubliBikeDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PubliBike integration from a config_old entry."""
    publi_bike = PubliBike()

    all_stations = await hass.async_add_executor_job(publi_bike.getStations)
    station = next(
        filter(
            lambda station: station.stationId == entry.data[STATION_ID], all_stations
        ),
        None,
    )
    if not station:
        raise ConfigEntryError("Station does not exists anymore")

    coordinator = PubliBikeDataUpdateCoordinator(
        hass, station, entry.options.get(BATTERY_LIMIT, BATTERY_LIMIT_DEFAULT)
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update for the PubliBike integration."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
