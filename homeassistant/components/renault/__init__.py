"""Support for Renault devices."""
import aiohttp
from renault_api.gigya.exceptions import GigyaException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_LOCALE, DOMAIN, PLATFORMS
from .renault_hub import RenaultHub
from .services import SERVICE_AC_START, setup_services, unload_services


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""
    renault_hub = RenaultHub(hass, entry.data[CONF_LOCALE])
    try:
        login_success = await renault_hub.attempt_login(
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )
    except (aiohttp.ClientConnectionError, GigyaException) as exc:
        raise ConfigEntryNotReady() from exc

    if not login_success:
        raise ConfigEntryAuthFailed()

    hass.data.setdefault(DOMAIN, {})
    await renault_hub.async_initialise(entry)

    hass.data[DOMAIN][entry.entry_id] = renault_hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, SERVICE_AC_START):
        setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            unload_services(hass)

    return unload_ok
