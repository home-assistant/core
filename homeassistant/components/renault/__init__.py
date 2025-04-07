"""Support for Renault devices."""

import aiohttp
from renault_api.gigya.exceptions import GigyaException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import CONF_LOCALE, DOMAIN, PLATFORMS
from .renault_hub import RenaultHub
from .services import setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
type RenaultConfigEntry = ConfigEntry[RenaultHub]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Renault component."""
    setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: RenaultConfigEntry
) -> bool:
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

    try:
        await renault_hub.async_initialise(config_entry)
    except aiohttp.ClientError as exc:
        raise ConfigEntryNotReady from exc

    config_entry.runtime_data = renault_hub

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: RenaultConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: RenaultConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return not device_entry.identifiers.intersection(
        (DOMAIN, vin) for vin in config_entry.runtime_data.vehicles
    )
