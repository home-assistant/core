"""The Cookidoo integration."""

from __future__ import annotations

from cookidoo_api import Cookidoo, CookidooConfig, CookidooLocalizationConfig

from homeassistant.const import (
    CONF_COUNTRY,
    CONF_EMAIL,
    CONF_LANGUAGE,
    CONF_PASSWORD,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import CookidooConfigEntry, CookidooDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.TODO]


async def async_setup_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Set up Cookidoo from a config entry."""

    cookidoo = Cookidoo(
        async_get_clientsession(hass),
        CookidooConfig(
            email=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            localization=CookidooLocalizationConfig(
                country_code=entry.data[CONF_COUNTRY].lower(),
                language=entry.data[CONF_LANGUAGE],
            ),
        ),
    )

    coordinator = CookidooDataUpdateCoordinator(hass, cookidoo, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
