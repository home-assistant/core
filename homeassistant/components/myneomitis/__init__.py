"""Integration for MyNeomitis."""

import logging

import pyaxencoapi

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["select"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up from configuration.yaml (not used)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyNeomitis from a config entry."""
    session = async_get_clientsession(hass)

    email: str = entry.data["email"]
    password: str = entry.data["password"]

    api = pyaxencoapi.PyAxencoAPI("myneomitis", session)
    try:
        await api.login(email, password)
        await api.connect_websocket()
        _LOGGER.info("MyNeomitis: Successfully connected to Login/WebSocket")

        # Retrieve the user's devices
        devices: list[dict] = await api.get_devices()

    except Exception as err:
        raise ConfigEntryNotReady(
            f"MyNeomitis: Error connecting to API/WebSocket: {err}"
        ) from err

    entry.runtime_data = {
        "api": api,
        "devices": devices,
    }

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.runtime_data

    # Load platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime_data = getattr(entry, "runtime_data", None)
        if runtime_data is None:
            runtime_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)

        api = None
        if isinstance(runtime_data, dict):
            api = runtime_data.get("api")

        if api is not None:
            try:
                await api.disconnect_websocket()
            except (TimeoutError, ConnectionError) as err:
                _LOGGER.error(
                    "MyNeomitis: Error while disconnecting WebSocket for %s: %s",
                    entry.entry_id,
                    err,
                )

        # Cleanup
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle reload of a config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
