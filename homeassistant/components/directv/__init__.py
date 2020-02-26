"""The DirecTV integration."""
import asyncio
from datetime import timedelta
from typing import Dict

from DirectPy import DIRECTV
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DATA_CLIENT, DATA_LOCATIONS, DATA_VERSION_INFO, DEFAULT_PORT, DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list, [vol.Schema({vol.Required(CONF_HOST): cv.string})]
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["media_player"]
SCAN_INTERVAL = timedelta(seconds=30)


def get_dtv_instance(
    host: str, port: int = DEFAULT_PORT, client_addr: str = "0"
) -> DIRECTV:
    """Retrieve a DIRECTV instance for the receiver device."""
    return DIRECTV(host, port, client_addr)


def get_dtv_locations(dtv: DIRECTV) -> Dict:
    """Retrieve the receiver locations list."""
    return dtv.get_locations()


def get_dtv_version(dtv: DIRECTV) -> Dict:
    """Retrieve the receiver version info."""
    return dtv.get_version()


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the DirecTV component."""
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
    """Set up DirecTV from a config entry."""
    try:
        # directpy does IO in constructor.
        dtv = await hass.async_add_executor_job(get_dtv_instance, entry.data[CONF_HOST])
        dtv_locations = await hass.async_add_executor_job(get_dtv_locations, dtv)
        dtv_version = await hass.async_add_executor_job(get_dtv_version, dtv)
    except (OSError, RequestException) as exception:
        raise ConfigEntryNotReady from exception
    except Exception as exception:  # pylint: disable=broad-except
        raise ConfigEntryNotReady from exception

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: dtv,
        DATA_LOCATIONS: dtv_locations,
        DATA_VERSION_INFO: dtv_version,
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
