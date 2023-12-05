"""EPS integration."""
import asyncio

from pyepsalarm import EPS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import EPSDataUpdateCoordinator

PLATFORMS = [Platform.ALARM_CONTROL_PANEL]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EPS config."""
    token: str = entry.data[CONF_TOKEN]
    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]
    eps_api = EPS(token, username, password)

    # Use the EPS siteId as a unique_id
    try:
        async with asyncio.timeout(10):
            site = await hass.async_add_executor_job(eps_api.get_site)
    except (asyncio.TimeoutError, ConnectionError) as ex:
        raise ConfigEntryNotReady from ex

    coordinator = EPSDataUpdateCoordinator(hass, eps_api, site)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload EPS config."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
