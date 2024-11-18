"""The SRP Energy integration."""

from srpenergy.client import SrpEnergyClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_IS_TOU, DOMAIN, LOGGER
from .coordinator import SRPEnergyDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SRP Energy component from a config entry."""
    api_account_id: str = entry.data[CONF_ID]
    api_username: str = entry.data[CONF_USERNAME]
    api_password: str = entry.data[CONF_PASSWORD]

    LOGGER.debug("Configuring client using account_id %s", api_account_id)

    api_instance = SrpEnergyClient(
        api_account_id,
        api_username,
        api_password,
    )

    coordinator = SRPEnergyDataUpdateCoordinator(
        hass, api_instance, entry.data[CONF_IS_TOU]
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
