"""Support for Renault devices."""
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_LOCALE, DOMAIN, PLATFORMS
from .renault_hub import RenaultHub


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Load a config entry."""
    renault_hub = RenaultHub(hass, config_entry.data[CONF_LOCALE])
    try:
        login_success = await renault_hub.attempt_login(
            config_entry.data[CONF_USERNAME], config_entry.data[CONF_PASSWORD]
        )
    except aiohttp.ClientConnectionError as exc:
        raise ConfigEntryNotReady() from exc

    if not login_success:
        return False

    hass.data.setdefault(DOMAIN, {})
    await renault_hub.async_initialise(config_entry)

    hass.data[DOMAIN][config_entry.unique_id] = renault_hub

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.unique_id)

    return unload_ok
