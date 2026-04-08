"""ROMY Integration."""

import romy

from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import LOGGER, PLATFORMS
from .coordinator import RomyConfigEntry, RomyVacuumCoordinator


async def async_setup_entry(hass: HomeAssistant, config_entry: RomyConfigEntry) -> bool:
    """Initialize the ROMY platform via config entry."""

    new_romy = await romy.create_romy(
        config_entry.data[CONF_HOST], config_entry.data.get(CONF_PASSWORD, "")
    )

    coordinator = RomyVacuumCoordinator(hass, config_entry, new_romy)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RomyConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, config_entry: RomyConfigEntry) -> None:
    """Handle options update."""
    LOGGER.debug("update_listener")
    await hass.config_entries.async_reload(config_entry.entry_id)
