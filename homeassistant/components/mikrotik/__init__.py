"""The Mikrotik component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import ATTR_MANUFACTURER, DOMAIN, PLATFORMS
from .hub import MikrotikDataUpdateCoordinator

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Mikrotik component."""

    hub = MikrotikDataUpdateCoordinator(hass, config_entry)
    if not await hub.async_setup():
        return False

    await hub.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = hub

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(DOMAIN, hub.serial_num)},
        manufacturer=ATTR_MANUFACTURER,
        model=hub.model,
        name=hub.hostname,
        sw_version=hub.firmware,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
