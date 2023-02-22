"""The zcs_azzurro integration."""
from __future__ import annotations

from zcs_azzurro_api import DeviceOfflineError, HttpRequestError, Inverter

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)

from .const import DOMAIN, SCHEMA_CLIENT_KEY, SCHEMA_FRIENDLY_NAME, SCHEMA_THINGS_KEY

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up zcs_azzurro from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    inverter = Inverter(
        client=entry.data[SCHEMA_CLIENT_KEY],
        thing_serial=entry.data[SCHEMA_THINGS_KEY],
        name=entry.data[SCHEMA_FRIENDLY_NAME],
    )
    try:
        if await hass.async_add_executor_job(inverter.check_connection):
            hass.data[DOMAIN][entry.entry_id] = inverter
            await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
            return True
        return False
    except HttpRequestError as excp:
        if excp.status_code in (401, 403):
            raise ConfigEntryAuthFailed(f"Not authorized: {excp}") from excp
        raise ConfigEntryNotReady(f"Connection error: {excp}") from excp
    except DeviceOfflineError as excp:
        raise ConfigEntryNotReady(f"No response: {excp}") from excp


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class ResponseError(HomeAssistantError):
    """Error to indicate there was a not ok response."""
