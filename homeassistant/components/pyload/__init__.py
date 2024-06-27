"""The pyLoad integration."""

from __future__ import annotations

from aiohttp import CookieJar
from pyloadapi.api import PyLoadAPI
from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN
from .coordinator import PyLoadCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]

type PyLoadConfigEntry = ConfigEntry[PyLoadCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PyLoadConfigEntry) -> bool:
    """Set up pyLoad from a config entry."""

    url = (
        f"{"https" if entry.data[CONF_SSL] else "http"}://"
        f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}/"
    )

    session = async_create_clientsession(
        hass,
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        cookie_jar=CookieJar(unsafe=True),
    )
    pyloadapi = PyLoadAPI(
        session,
        api_url=url,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        await pyloadapi.login()
    except CannotConnect as e:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_request_exception",
        ) from e
    except ParserError as e:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_parse_exception",
        ) from e
    except InvalidAuth as e:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="setup_authentication_exception",
            translation_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
        ) from e
    coordinator = PyLoadCoordinator(hass, pyloadapi)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PyLoadConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
