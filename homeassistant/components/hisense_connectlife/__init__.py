"""The Hisense ConnectLife integration."""
from __future__ import annotations

import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HisenseApiClient
from .const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN, CLIENT_ID, CLIENT_SECRET
from .oauth2 import HisenseOAuth2Implementation, OAuth2Session
from .coordinator import HisenseACPluginDataUpdateCoordinator
from .config_flow import OAuth2FlowHandler

_LOGGER = logging.getLogger(__name__)

# This integration can only be configured via config entry
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SWITCH, Platform.WATER_HEATER, Platform.NUMBER, Platform.SENSOR, Platform.HUMIDIFIER]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hisense AC Plugin component."""
    _LOGGER.debug("Setting up Hisense AC Plugin")

    hass.data.setdefault(DOMAIN, {})

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

    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )
    
    # Create Home Assistant's OAuth2Session for token management
    ha_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    
    # Get the token data and add expiration time
    token_info = await ha_session.async_ensure_token_valid()
    if token_info is None:
        token_info = entry.data.get("token", {})
    
    if "expires_in" in token_info and "expires_at" not in token_info:
        token_info["expires_at"] = time.time() + token_info["expires_in"]
    
    _LOGGER.debug("Token info: %s", {
        k: '***' if k in ('access_token', 'refresh_token') else v 
        for k, v in token_info.items()
    })
    
    # Create our custom OAuth2Session that wraps the HA session
    oauth_session = OAuth2Session(
        hass=hass,
        oauth2_implementation=implementation,
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

    # Store coordinator in hass.data
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.api_client.oauth_session.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok