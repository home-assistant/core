"""The Cookidoo integration."""

from __future__ import annotations

from cookidoo_api import DEFAULT_COOKIDOO_CONFIG, Cookidoo, get_localization_options

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LOCALIZATION
from .coordinator import CookidooConfigEntry, CookidooDataUpdateCoordinator
from .helpers import cookidoo_localization_for_key

PLATFORMS: list[Platform] = [Platform.TODO]


async def async_setup_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Set up Cookidoo from a config entry."""

    cookidoo = Cookidoo(
        async_get_clientsession(hass),
        {
            **DEFAULT_COOKIDOO_CONFIG,
            CONF_EMAIL: entry.data[CONF_EMAIL],
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
            CONF_LOCALIZATION: cookidoo_localization_for_key(
                await get_localization_options(), entry.data[CONF_LOCALIZATION]
            ),
        },
    )

    coordinator = CookidooDataUpdateCoordinator(hass, cookidoo, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
