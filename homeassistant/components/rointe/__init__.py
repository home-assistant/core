"""The Rointe Heaters integration."""
from __future__ import annotations

from rointesdk.rointe_api import ApiResponse, RointeAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_INSTALLATION, CONF_PASSWORD, CONF_USERNAME, DOMAIN, PLATFORMS
from .coordinator import RointeDataUpdateCoordinator
from .device_manager import RointeDeviceManager


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rointe Heaters from a config entry."""

    rointe_api = RointeAPI(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])

    # Login to the Rointe API.
    login_result: ApiResponse = await hass.async_add_executor_job(
        rointe_api.initialize_authentication
    )

    if not login_result.success:
        raise ConfigEntryNotReady("Unable to connect to the Rointe API")

    rointe_device_manager = RointeDeviceManager(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        installation_id=entry.data[CONF_INSTALLATION],
        hass=hass,
        rointe_api=rointe_api,
    )

    rointe_coordinator = RointeDataUpdateCoordinator(hass, rointe_device_manager)

    await rointe_coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = rointe_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and removes event handlers."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
