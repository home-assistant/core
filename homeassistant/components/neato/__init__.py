"""Support for Neato botvac connected vacuum cleaners."""

import logging

from aiohttp import ClientError
from pybotvac import Account
from pybotvac.exceptions import NeatoException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from . import api
from .const import DOMAIN
from .hub import NeatoHub
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

type NeatoConfigEntry = ConfigEntry[NeatoHub]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NeatoConfigEntry) -> bool:
    """Set up config entry."""
    if CONF_TOKEN not in entry.data:
        raise ConfigEntryAuthFailed

    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    session = OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as ex:
        raise ConfigEntryAuthFailed from ex
    except (OAuth2TokenRequestError, ClientError) as ex:
        raise ConfigEntryNotReady from ex

    neato_session = api.ConfigEntryAuth(hass, entry, implementation)
    hub = NeatoHub(hass, Account(neato_session))

    await hub.async_update_entry_unique_id(entry)

    try:
        await hass.async_add_executor_job(hub.update_robots)
    except NeatoException as ex:
        _LOGGER.debug("Failed to connect to Neato API")
        raise ConfigEntryNotReady from ex

    entry.runtime_data = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NeatoConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
