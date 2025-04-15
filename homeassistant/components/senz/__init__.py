"""The nVent RAYCHEM SENZ integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiosenz import SENZAPI, Thermostat
from httpx import RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    httpx_client,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SENZConfigEntryAuth
from .const import DOMAIN

UPDATE_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.CLIMATE]

type SENZDataUpdateCoordinator = DataUpdateCoordinator[dict[str, Thermostat]]


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

    coordinator: SENZDataUpdateCoordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=account.username,
        update_interval=UPDATE_INTERVAL,
        update_method=update_thermostats,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
