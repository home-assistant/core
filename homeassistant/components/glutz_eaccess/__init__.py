"""The Glutz eAccess integration."""
from __future__ import annotations

from pyglutz_eaccess import GlutzAPI

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import GlutzConfigEntry, GlutzCoordinator

PLATFORMS = [Platform.LOCK]


async def async_setup_entry(hass: HomeAssistant, entry: GlutzConfigEntry) -> bool:
    """Set up Glutz eAccess from a config entry."""
    api = GlutzAPI(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        language=hass.config.language,
    )
    coordinator = GlutzCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GlutzConfigEntry) -> bool:
    """Unload a Glutz eAccess config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: GlutzConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow removal of a device whose access point no longer exists."""
    coordinator = entry.runtime_data
    return not any(
        identifier[1] in coordinator.data
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
    )
