"""The Bring! integration."""

from __future__ import annotations

import logging

from bring_api import (
    Bring,
    BringAuthException,
    BringParseException,
    BringRequestException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import BringDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.TODO]

_LOGGER = logging.getLogger(__name__)

type BringConfigEntry = ConfigEntry[BringDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BringConfigEntry) -> bool:
    """Set up Bring! from a config entry."""

    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    session = async_get_clientsession(hass)
    bring = Bring(session, email, password)

    try:
        await bring.login()
    except BringRequestException as e:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_request_exception",
        ) from e
    except BringParseException as e:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_parse_exception",
        ) from e
    except BringAuthException as e:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="setup_authentication_exception",
            translation_placeholders={CONF_EMAIL: email},
        ) from e

    coordinator = BringDataUpdateCoordinator(hass, bring)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
