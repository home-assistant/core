"""Helpers for cookidoo."""

from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from aiohttp import CookieJar
from cookidoo_api import (
    Cookidoo,
    CookidooAuthData,
    CookidooConfig,
    get_localization_options,
)

from homeassistant.const import (
    CONF_COUNTRY,
    CONF_EMAIL,
    CONF_LANGUAGE,
    CONF_PASSWORD,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .coordinator import CookidooConfigEntry


async def cookidoo_from_config_data(
    hass: HomeAssistant,
    data: dict[str, Any],
    on_auth_data_update: Callable[[CookidooAuthData], None] | None = None,
) -> Cookidoo:
    """Build cookidoo from config data."""
    localizations = await get_localization_options(
        country=data[CONF_COUNTRY].lower(),
        language=data[CONF_LANGUAGE],
    )

    return Cookidoo(
        async_create_clientsession(hass, cookie_jar=CookieJar(unsafe=True)),
        CookidooConfig(
            email=data[CONF_EMAIL],
            password=data[CONF_PASSWORD],
            localization=localizations[0],
        ),
        on_auth_data_update=on_auth_data_update,
    )


async def cookidoo_from_config_entry(
    hass: HomeAssistant, entry: CookidooConfigEntry
) -> Cookidoo:
    """Build cookidoo from config entry."""

    @callback
    def save_auth_data(auth_data: CookidooAuthData) -> None:
        """Store the tokens, so a restart does not need a new login."""
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_TOKEN: asdict(auth_data)}
        )

    cookidoo = await cookidoo_from_config_data(
        hass, dict(entry.data), on_auth_data_update=save_auth_data
    )
    if token := entry.data.get(CONF_TOKEN):
        cookidoo.apply_auth_data(CookidooAuthData(**token))
    return cookidoo
