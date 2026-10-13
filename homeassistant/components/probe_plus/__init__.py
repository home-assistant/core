"""The Probe Plus integration."""

from homeassistant.const import CONF_MODEL, Platform
from homeassistant.core import HomeAssistant

from .coordinator import ProbePlusConfigEntry, ProbePlusDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ProbePlusConfigEntry) -> None:
    """Set up Probe Plus from a config entry."""
    # Perform a migration to ensure the model is added to the config entry schema.
    if CONF_MODEL not in entry.data:
        # The config entry adds the model number of the device to the start of its title
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_MODEL: entry.title.split(" ")[0]}
        )
    coordinator = ProbePlusDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ProbePlusConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
