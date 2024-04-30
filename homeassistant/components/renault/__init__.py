"""Support for Renault devices."""

import aiohttp
from renault_api.gigya.exceptions import GigyaException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_LOCALE, DOMAIN, PLATFORMS
from .renault_hub import RenaultHub
from .services import setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Renault component."""
    setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Load a config entry."""
    renault_hub = RenaultHub(hass, config_entry.data[CONF_LOCALE])
    try:
        login_success = await renault_hub.attempt_login(
            config_entry.data[CONF_USERNAME], config_entry.data[CONF_PASSWORD]
        )
    except (aiohttp.ClientConnectionError, GigyaException) as exc:
        raise ConfigEntryNotReady from exc

    if not login_success:
        raise ConfigEntryAuthFailed

    hass.data.setdefault(DOMAIN, {})
    try:
        await renault_hub.async_initialise(config_entry)
    except aiohttp.ClientError as exc:
        raise ConfigEntryNotReady from exc

    hass.data[DOMAIN][config_entry.entry_id] = renault_hub

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
