"""Comelit integration."""

from aiocomelit.const import BRIDGE

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PIN, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import _LOGGER, DEFAULT_PORT, DOMAIN
from .coordinator import ComelitSerialBridge

PLATFORMS = [Platform.COVER, Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Comelit platform."""
    coordinator = ComelitSerialBridge(
        hass, entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_PIN]
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        new_data = entry.data.copy()
        new_data.update({CONF_PORT: DEFAULT_PORT, CONF_DEVICE: BRIDGE})

        entry.version = 2
        hass.config_entries.async_update_entry(entry, data=new_data)

    _LOGGER.info("Migration to version %s successful", entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: ComelitSerialBridge = hass.data[DOMAIN][entry.entry_id]
        await coordinator.api.logout()
        await coordinator.api.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
