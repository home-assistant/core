"""The Bitvis Power Hub integration."""

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .coordinator import BitvisConfigEntry, BitvisDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BitvisConfigEntry) -> bool:
    """Set up Bitvis Power Hub from a config entry."""
    unique_id = entry.unique_id
    assert unique_id is not None
    coordinator = BitvisDataUpdateCoordinator(
        hass,
        entry,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        unique_id,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_stop)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BitvisConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
