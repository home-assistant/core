"""The Theben Conexa Smartmeter gateway integration."""

import aiohttp
from theben_conexa_smgw import checkNetworkConnection

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .coordinator import SmgwSensorCoordinator, ThebenConfigEntry

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ThebenConfigEntry) -> bool:
    """Set up Theben Conexa Smartmeter gateway from a config entry."""

    try:
        # This function tries to establish a TCP connection and raises an exception on error
        await checkNetworkConnection(entry.data[CONF_HOST])
    except (OSError, aiohttp.ClientError) as e:
        raise ConfigEntryNotReady("Device is not reachable") from e

    try:
        # Unfortunately the Conexa 3.0 doesn't provide separate authentication feedback it just ignores all requests with invalid username/password,
        # That's why here we need to assume it failed because of wrong credentials, as we checked for connectivity just before and the device was reachable.
        coordinator = SmgwSensorCoordinator(hass, entry)
        await coordinator.async_init()
        entry.runtime_data = coordinator

    except (OSError, aiohttp.ClientError) as e:
        raise ConfigEntryAuthFailed("Authentication failed") from e

    # Get initial data
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ThebenConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
