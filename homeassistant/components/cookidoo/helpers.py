"""Helpers for cookidoo."""

from typing import Any

from cookidoo_api import Cookidoo, CookidooConfig, get_localization_options

from homeassistant.const import CONF_COUNTRY, CONF_EMAIL, CONF_LANGUAGE, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import CookidooConfigEntry


async def cookidoo_from_config_data(
    hass: HomeAssistant, data: dict[str, Any]
) -> Cookidoo:
    """Build cookidoo from config data."""
    localizations = await get_localization_options(
        country=data[CONF_COUNTRY].lower(),
        language=data[CONF_LANGUAGE],
    )

    return Cookidoo(
        async_get_clientsession(hass),
        CookidooConfig(
            email=data[CONF_EMAIL],
            password=data[CONF_PASSWORD],
            localization=localizations[0],
        ),
    )


async def cookidoo_from_config_entry(
    hass: HomeAssistant, entry: CookidooConfigEntry
) -> Cookidoo:
    """Build cookidoo from config entry."""
    return await cookidoo_from_config_data(hass, dict(entry.data))
