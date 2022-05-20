"""The IntelliFire integration."""
from __future__ import annotations

from aiohttp import ClientConnectionError
from intellifire4py import IntellifireControlAsync
from intellifire4py.exceptions import LoginException
from intellifire4py.intellifire import IntellifireAPICloud, IntellifireAPILocal
from intellifire4py.read_async import IntellifireAsync

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_USER_ID, DOMAIN, LOGGER
from .coordinator import IntellifireDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]


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

    # Extract API Key and User_ID from ift_control
    # Eventually this will migrate to using IntellifireAPICloud

    user_id = ift_control.get_username
    api_key = ift_control.default_fireplace.apikey

    # Instantiate local control
    api = IntellifireAPILocal(
        fireplace_ip=entry.data[CONF_HOST], api_key=api_key, user_id=user_id
    )

    # Define the update coordinator
    coordinator = IntellifireDataUpdateCoordinator(
        hass=hass, api=api, control_api=ift_control
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
