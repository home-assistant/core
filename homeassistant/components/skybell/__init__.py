"""Support for the Skybell HD Doorbell."""
from __future__ import annotations

import asyncio
import os

from aioskybell import Skybell
from aioskybell.exceptions import SkybellAuthenticationException, SkybellException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_CACHEDB, DOMAIN
from .coordinator import SkybellDataUpdateCoordinator

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        # Deprecated in Home Assistant 2022.6
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SkyBell component."""
    hass.data.setdefault(DOMAIN, {})

    entry_config = {}
    if DOMAIN not in config:
        return True
    for parameter, value in config[DOMAIN].items():
        if parameter == CONF_USERNAME:
            entry_config[CONF_EMAIL] = value
        else:
            entry_config[parameter] = value
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=entry_config,
            )
        )

    # Clean up unused cache file since we are using an account specific name
    # Remove with import
    def clean_cache():
        """Clean old cache filename."""
        if os.path.exists(hass.config.path(DEFAULT_CACHEDB)):
            os.remove(hass.config.path(DEFAULT_CACHEDB))

    await hass.async_add_executor_job(clean_cache)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Skybell from a config entry."""
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    api = Skybell(
        username=email,
        password=password,
        get_devices=True,
        cache_path=hass.config.path(f"./skybell_{entry.unique_id}.pickle"),
        session=async_get_clientsession(hass),
    )
    try:
        devices = await api.async_initialize()
    except SkybellAuthenticationException:
        return False
    except SkybellException as ex:
        raise ConfigEntryNotReady(f"Unable to connect to Skybell service: {ex}") from ex

    device_coordinators: list[SkybellDataUpdateCoordinator] = [
        SkybellDataUpdateCoordinator(hass, device) for device in devices
    ]
    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in device_coordinators
        ]
    )
    hass.data[DOMAIN][entry.entry_id] = device_coordinators
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
