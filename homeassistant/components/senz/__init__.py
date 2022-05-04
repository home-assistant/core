"""The nVent RAYCHEM SENZ integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiosenz import AUTHORIZATION_ENDPOINT, SENZAPI, TOKEN_ENDPOINT, Thermostat
from httpx import RequestError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    httpx_client,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import config_flow
from .api import SENZConfigEntryAuth
from .const import DOMAIN

UPDATE_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.CLIMATE]

SENZDataUpdateCoordinator = DataUpdateCoordinator[dict[str, Thermostat]]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SENZ OAuth2 configuration."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            AUTHORIZATION_ENDPOINT,
            TOKEN_ENDPOINT,
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SENZ from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    auth = SENZConfigEntryAuth(httpx_client.get_async_client(hass), session)
    senz_api = SENZAPI(auth)

    async def update_thermostats() -> dict[str, Thermostat]:
        """Fetch SENZ thermostats data."""
        try:
            thermostats = await senz_api.get_thermostats()
        except RequestError as err:
            raise UpdateFailed from err
        return {thermostat.serial_number: thermostat for thermostat in thermostats}

    try:
        account = await senz_api.get_account()
    except RequestError as err:
        raise ConfigEntryNotReady from err

    coordinator = SENZDataUpdateCoordinator(
        hass,
        _LOGGER,
        name=account.username,
        update_interval=UPDATE_INTERVAL,
        update_method=update_thermostats,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
