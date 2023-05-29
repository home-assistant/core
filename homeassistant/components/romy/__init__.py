"""ROMY Integration."""

import romy

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER, PLATFORMS
from .coordinator import RomyVacuumCoordinator


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """TODO."""

    password = ""
    if CONF_PASSWORD in config_entry.data:
        password = config_entry.data[CONF_PASSWORD]

    new_romy = await romy.create_romy(config_entry.data[CONF_HOST], password)

    name = config_entry.data[CONF_NAME]
    if name != new_romy.name:
        await new_romy.set_name(name)
        LOGGER.info("Settings ROMY's name to: %s", new_romy.name)

    coordinator = RomyVacuumCoordinator(hass, new_romy)
    await coordinator.async_config_entry_first_refresh()

    # hass.data.setdefault(DOMAIN, {})
    # hass.data[DOMAIN][config_entry.entry_id] = coordinator
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    return unload_ok
