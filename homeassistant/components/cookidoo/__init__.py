"""The Cookidoo integration."""

from __future__ import annotations

from cookidoo_api import (
    DEFAULT_COOKIDOO_CONFIG,
    Cookidoo,
    CookidooAuthException,
    CookidooRequestException,
    get_localization_options,
)

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LOCALIZATION, DOMAIN
from .coordinator import CookidooConfigEntry, CookidooDataUpdateCoordinator
from .helpers import cookidoo_localization_for_key

PLATFORMS: list[Platform] = [Platform.TODO]


async def async_setup_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Set up Cookidoo from a config entry."""

    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    localization = cookidoo_localization_for_key(
        await get_localization_options(), entry.data[CONF_LOCALIZATION]
    )
    session = async_get_clientsession(hass)
    cookidoo = Cookidoo(
        session,
        {
            **DEFAULT_COOKIDOO_CONFIG,
            "localization": localization,
            "email": email,
            "password": password,
        },
    )

    try:
        await cookidoo.login()
    except CookidooRequestException as e:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_request_exception",
        ) from e
    except CookidooAuthException as e:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="setup_authentication_exception",
            translation_placeholders={CONF_EMAIL: email},
        ) from e

    coordinator = CookidooDataUpdateCoordinator(hass, cookidoo)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
