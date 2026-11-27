"""Initialize the Fuelprices.dk component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import FuelPricesDKCoordinator

PLATFORMS = [Platform.SENSOR]

type FuelpricesDkConfigEntry = ConfigEntry[FuelPricesDKCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: FuelpricesDkConfigEntry
) -> None:
    """Set up Fuelprices.dk from a config entry."""
    config_entry.async_on_unload(config_entry.add_update_listener(_update_listener))
    coordinator = FuelPricesDKCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)


async def _update_listener(hass: HomeAssistant, entry: FuelpricesDkConfigEntry) -> None:
    """Handle options or subentry updates by reloading the entry."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: FuelpricesDkConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)
