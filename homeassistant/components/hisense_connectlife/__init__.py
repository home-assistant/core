"""The Hisense ConnectLife integration."""

from __future__ import annotations

import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import HisenseApiClient
from .config_flow import OAuth2FlowHandler
from .const import DOMAIN
from .coordinator import HisenseACPluginDataUpdateCoordinator
from .oauth2 import HisenseOAuth2Implementation, OAuth2Session

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
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
    except config_entry_oauth2_flow.ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            "OAuth2 implementation temporarily unavailable"
        ) from err

    ha_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    await ha_session.async_ensure_token_valid()

    token_info = entry.data.get("token", {})
    if "expires_in" in token_info:
        token_info["expires_at"] = time.time() + token_info["expires_in"]

    hisense_impl = HisenseOAuth2Implementation(hass)
    oauth_session = OAuth2Session(
        hass=hass, oauth2_implementation=hisense_impl, token=token_info
    )
    api_client = HisenseApiClient(hass, oauth_session)

    coordinator = HisenseACPluginDataUpdateCoordinator(hass, api_client, entry)

    await coordinator.async_config_entry_first_refresh()

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
