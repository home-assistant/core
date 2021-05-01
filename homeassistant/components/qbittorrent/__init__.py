"""The qbittorrent component."""
import asyncio
import logging

from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_per_platform

from .client import create_client
from .const import DATA_KEY_CLIENT, DATA_KEY_NAME, DOMAIN

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Qbittorrent component."""
    hass.data.setdefault(DOMAIN, {})

    # Import configuration from sensor platform
    config_platform = config_per_platform(config, "sensor")
    for p_type, p_config in config_platform:
        if p_type != DOMAIN:
            continue

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=p_config,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Qbittorrent from a config entry."""
    name = "Qbittorrent"
    try:
        client = await hass.async_add_executor_job(
            create_client,
            entry.data[CONF_URL],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        )
    except LoginRequired:
        _LOGGER.error("Invalid authentication")
        return

    except RequestException as err:
        _LOGGER.error("Connection failed")
        raise PlatformNotReady from err

    hass.data[DOMAIN][entry.data[CONF_URL]] = {
        DATA_KEY_CLIENT: client,
        DATA_KEY_NAME: name,
    }
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload Qbittorrent Entry from config_entry."""

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    return unload_ok
