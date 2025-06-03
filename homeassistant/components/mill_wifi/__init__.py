import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from .const import DOMAIN
from .coordinator import MillDataCoordinator
from .api import MillApiClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch", "number", "climate", "select"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mill WiFi from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    api = MillApiClient(username, password)

    await api.async_setup()
    try:
        await api.login()
    except Exception as e:
        _LOGGER.error("Failed to login to Mill API during setup: %s", e)
        return False

    coordinator = MillDataCoordinator(hass, api)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        mill_data = hass.data[DOMAIN].pop(entry.entry_id)
        api: MillApiClient = mill_data["api"]
        await api.async_close()

    return unload_ok
