"""Initialize the Fuelprices.dk component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_COMPANY, CONF_STATION
from .coordinator import APIClient

PLATFORMS = [Platform.SENSOR]

type FuelpricesDkRuntimeData = dict[str, APIClient]
type FuelpricesDkConfigEntry = ConfigEntry[FuelpricesDkRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: FuelpricesDkConfigEntry
) -> bool:
    """Set up Fuelprices.dk from a config entry."""
    config_entry.async_on_unload(config_entry.add_update_listener(_update_listener))
    api_key = config_entry.data[CONF_API_KEY]
    runtime_data: FuelpricesDkRuntimeData = {}

    for subentry_id, subentry in config_entry.subentries.items():
        if subentry.subentry_type != "station":
            continue

        company = subentry.data[CONF_COMPANY]
        station = subentry.data[CONF_STATION]

        coordinator = APIClient(
            hass,
            api_key,
            company,
            station,
            subentry_id,
            config_entry,
        )
        runtime_data[subentry_id] = coordinator
        await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = runtime_data
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def _update_listener(hass: HomeAssistant, entry: FuelpricesDkConfigEntry) -> None:
    """Handle options or subentry updates by reloading the entry."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: FuelpricesDkConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
