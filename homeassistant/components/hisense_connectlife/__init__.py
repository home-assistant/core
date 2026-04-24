"""The Hisense ConnectLife integration."""

from __future__ import annotations

import logging

from aiohttp.client_exceptions import ClientError, ClientResponseError
from connectlife_cloud import HisenseApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .config_flow import OAuth2FlowHandler
from .const import DOMAIN
from .coordinator import HisenseACPluginDataUpdateCoordinator
from .oauth2 import HisenseOAuth2Implementation

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hisense ConnectLife."""
    _LOGGER.debug("Setting up Hisense ConnectLife")

    OAuth2FlowHandler.async_register_implementation(
        hass,
        HisenseOAuth2Implementation(hass),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hisense AC Plugin from a config entry."""
    _LOGGER.debug("Setting up config entry: %s", entry.title)

    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            "OAuth2 implementation temporarily unavailable"
        ) from err

    ha_session = OAuth2Session(hass, entry, implementation)
    await ha_session.async_ensure_token_valid()

    session = OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(
                "OAuth session is not valid, reauth required"
            ) from err
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err
    access_token = entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]

    api_client = HisenseApiClient(token=access_token)

    coordinator = HisenseACPluginDataUpdateCoordinator(hass, api_client, entry)

    await coordinator.async_setup()

    _LOGGER.debug("Initial data refresh successful during setup")

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        await coordinator.api_client.oauth_session.close()
        entry.runtime_data = None

    return unload_ok
