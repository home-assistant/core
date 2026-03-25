"""The aurora component."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_THRESHOLD, DEFAULT_THRESHOLD
from .coordinator import AuroraConfigEntry, AuroraDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AuroraConfigEntry) -> bool:
    """Set up Aurora from a config entry."""
    coordinator = AuroraDataUpdateCoordinator(hass=hass, config_entry=entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def update_listener(hass: HomeAssistant, entry: AuroraConfigEntry) -> None:
    """Handle options update."""
    entry.runtime_data.threshold = int(
        entry.options.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)
    )
    # refresh the state of the visibility alert binary sensor
    await entry.runtime_data.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: AuroraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
