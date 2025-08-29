"""Integration for MyNeomitis."""

import logging

import pyaxencoapi

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate", "select", "sensor"]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up from configuration.yaml (not used)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyNeomitis from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (ConfigEntry): The configuration entry.

    Returns:
        bool: True if the setup was successful.

    """
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)

    email: str = entry.data["email"]
    password: str = entry.data["password"]

    api = pyaxencoapi.PyAxencoAPI("myneomitis", session)
    try:
        await api.login(email, password)  # Token renewal
        await api.connect_websocket()
        _LOGGER.info("MyNeomitis : Success Connection to Login/Websocket")
        # Retrieve the user's devices
        devices: list[dict] = await api.get_devices()

    except Exception as err:
        raise ConfigEntryNotReady(f"MyNeomitis : Error Login/Websocket : {err}") from err

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "devices": devices,
    }

    # Launch the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle the unloading of a configuration entry.

    This function is responsible for unloading platforms associated with the
    configuration entry and cleaning up resources such as WebSocket connections.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (ConfigEntry): The configuration entry to unload.

    Returns:
        bool: True if the unloading was successful, False otherwise.

    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain_data = hass.data.get(DOMAIN, {})
        if entry.entry_id in domain_data:
            api = domain_data[entry.entry_id].get("api")
            try:
                await api.disconnect_websocket()
            except (TimeoutError, ConnectionError) as err:
                _LOGGER.error(
                    "MyNeomitis : Error while disconnecting WebSocket for %s: %s",
                    entry.entry_id,
                    err,
                )
            # Remove the entry
            domain_data.pop(entry.entry_id)
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry.

    This is typically triggered when the user reloads the integration from the UI.
    It will unload and then re-setup the entry cleanly.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (ConfigEntry): The configuration entry to reload.

    """
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
