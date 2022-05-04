"""The IntelliFire integration."""
from __future__ import annotations

from aiohttp import ClientConnectionError
from intellifire4py import IntellifireAsync, IntellifireControlAsync
from intellifire4py.exceptions import LoginException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN, LOGGER
from .coordinator import IntellifireDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IntelliFire from a config entry."""
    LOGGER.debug("Setting up config entry: %s", entry.unique_id)

    if CONF_USERNAME not in entry.data:
        LOGGER.debug("Old config entry format detected: %s", entry.unique_id)
        raise ConfigEntryAuthFailed

    # Define the API Objects
    read_object = IntellifireAsync(entry.data[CONF_HOST])
    ift_control = IntellifireControlAsync(
        fireplace_ip=entry.data[CONF_HOST],
    )
    try:
        await ift_control.login(
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
        )
    except (ConnectionError, ClientConnectionError) as err:
        raise ConfigEntryNotReady from err
    except LoginException as err:
        raise ConfigEntryAuthFailed(err) from err

    finally:
        await ift_control.close()

    # Define the update coordinator
    coordinator = IntellifireDataUpdateCoordinator(
        hass=hass, read_api=read_object, control_api=ift_control
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
