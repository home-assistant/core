"""Support for Renault devices."""
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import HomeAssistantType

from .const import CONF_KAMEREON_ACCOUNT_ID, CONF_LOCALE, DOMAIN, SUPPORTED_PLATFORMS
from .renault_hub import RenaultHub


async def async_setup(hass, config):
    """Set up renault integrations."""
    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry):
    """Load a config entry."""
    hass.data.setdefault(DOMAIN, {})

    renault_hub = RenaultHub(hass, config_entry.data[CONF_LOCALE])
    try:
        login_success = await renault_hub.attempt_login(
            config_entry.data[CONF_USERNAME], config_entry.data[CONF_PASSWORD]
        )
    except aiohttp.ClientConnectionError as exc:
        raise ConfigEntryNotReady() from exc

    if not login_success:
        return False

    await renault_hub.set_account_id(config_entry.data[CONF_KAMEREON_ACCOUNT_ID])

    hass.data[DOMAIN][config_entry.unique_id] = renault_hub

    for component in SUPPORTED_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = True

    for component in SUPPORTED_PLATFORMS:
        unload_ok = unload_ok and await hass.config_entries.async_forward_entry_unload(
            config_entry, component
        )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.unique_id)

    return unload_ok
