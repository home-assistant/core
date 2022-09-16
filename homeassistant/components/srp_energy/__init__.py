"""The SRP Energy integration."""
from srpenergy.client import SrpEnergyClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import (  # noqa: F401
    ATTRIBUTION,
    CONF_IS_TOU,
    DEFAULT_NAME,
    DOMAIN,
    ICON,
    LOGGER,
    SENSOR_NAME,
    SENSOR_TYPE,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SRP Energy component from a config entry."""
    api_account_id: str = entry.data[CONF_ID]
    api_username: str = entry.data[CONF_USERNAME]
    api_password: str = entry.data[CONF_PASSWORD]
    name: str = entry.title

    LOGGER.debug("%s Using account_id %s", name, api_account_id)

    api_instance = SrpEnergyClient(
        api_account_id,
        api_username,
        api_password,
    )

    LOGGER.debug("async_setup_entry: Client Details: %s", type(api_instance))
    LOGGER.debug("async_setup_entry: Client attributes: %s", dir(api_instance))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api_instance

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
