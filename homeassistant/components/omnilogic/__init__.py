"""The Omnilogic integration."""
import asyncio
from datetime import timedelta
import logging

from omnilogic import LoginException, OmniLogic, OmniLogicException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COORDINATOR, DOMAIN, OMNI_API, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Omnilogic component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Omnilogic from a config entry."""

    conf = entry.data
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    polling_interval = conf[POLL_INTERVAL]
    api = OmniLogic(username, password)

    try:
        await api.connect()
        await api.get_telemetry_data()
    except LoginException as e:
        _LOGGER.debug(f"OmniLogic login error: {e}")
        raise PlatformNotReady
    except OmniLogicException as e:
        _LOGGER.debug(f"OmniLogic API error: {e}")

    async def async_update_data():
        """Fetch data from API endpoint."""
        _LOGGER.debug("Updating the coordinator data.")
        try:
            data = await api.get_telemetry_data()
            return data
        except OmniLogicException as e:
            _LOGGER.debug(f"OmniLogic API error: {e}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Omnilogic",
        update_method=async_update_data,
        update_interval=timedelta(seconds=polling_interval),
    )

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        OMNI_API: api,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
