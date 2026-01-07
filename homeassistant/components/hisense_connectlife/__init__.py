"""The Hisense ConnectLife integration."""

from __future__ import annotations

import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import HisenseApiClient
from .config_flow import OAuth2FlowHandler
from .const import DOMAIN
from .coordinator import HisenseACPluginDataUpdateCoordinator
from .oauth2 import HisenseOAuth2Implementation, OAuth2Session

_LOGGER = logging.getLogger(__name__)

# This integration can only be configured via config entry
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hisense AC Plugin component."""
    _LOGGER.debug("Setting up Hisense AC Plugin")

    implementation = HisenseOAuth2Implementation(
        hass,
    )

    OAuth2FlowHandler.async_register_implementation(
        hass,
        implementation,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hisense AC Plugin from a config entry."""
    _LOGGER.debug("Setting up config entry: %s", entry.title)

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    # Create Home Assistant's OAuth2Session for token management
    ha_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    # Ensure token is valid
    await ha_session.async_ensure_token_valid()
    token_info = entry.data.get("token", {})

    if "expires_in" in token_info and "expires_at" not in token_info:
        token_info["expires_at"] = time.time() + token_info["expires_in"]

    _LOGGER.debug(
        "Token info: %s",
        {
            k: "***" if k in ("access_token", "refresh_token") else v
            for k, v in token_info.items()
        },
    )

    # Get the implementation as HisenseOAuth2Implementation
    hisense_impl = HisenseOAuth2Implementation(hass)

    # Create our custom OAuth2Session that wraps the HA session
    oauth_session = OAuth2Session(
        hass=hass,
        oauth2_implementation=hisense_impl,
        token=token_info,
    )

    # Create API client
    api_client = HisenseApiClient(hass, oauth_session)

    # Create update coordinator
    coordinator = HisenseACPluginDataUpdateCoordinator(hass, api_client, entry)

    # Initialize coordinator and get initial device list
    if not await coordinator.async_setup():
        _LOGGER.error("Failed to setup coordinator")
        return False

    # Store coordinator in entry.runtime_data
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
