"""Support for Roku."""
import asyncio
from datetime import timedelta
from typing import Dict

from roku import Roku, RokuException
import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DATA_CLIENT, DATA_DEVICE_INFO, DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list, [vol.Schema({vol.Required(CONF_HOST): cv.string})]
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [MEDIA_PLAYER_DOMAIN, REMOTE_DOMAIN]
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the Roku integration."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN in config:
        for entry_config in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_config,
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Roku from a config entry."""
    try:
        roku = Roku(entry.data[CONF_HOST])
        roku_device_info = await async_add_executor_job(roku.device_info)
    except (OSError, RokuException) as exception:
        raise ConfigEntryNotReady from exception
    except Exception as exception:  # pylint: disable=broad-except
        raise ConfigEntryNotReady from exception

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: roku,
        DATA_DEVICE_INFO: roku_device_info,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
