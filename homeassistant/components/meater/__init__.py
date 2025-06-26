"""The Meater Temperature Probe integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import MEATER_DATA
from .coordinator import MeaterConfigEntry, MeaterCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MeaterConfigEntry) -> bool:
    """Set up Meater Temperature Probe from a config entry."""

    coordinator = MeaterCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(MEATER_DATA, set())

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeaterConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[MEATER_DATA] = (
            hass.data[MEATER_DATA] - entry.runtime_data.found_probes
        )
    return unload_ok
