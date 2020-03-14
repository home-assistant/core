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


def get_dtv_data(
    hass: HomeAssistant, host: str, port: int = DEFAULT_PORT, client_addr: str = "0"
) -> dict:
    """Retrieve a DIRECTV instance, locations list, and version info for the receiver device."""
    dtv = DIRECTV(host, port, client_addr, determine_state=False)
    locations = dtv.get_locations()
    version_info = dtv.get_version()

    return {
        DATA_CLIENT: dtv,
        DATA_LOCATIONS: locations,
        DATA_VERSION_INFO: version_info,
    }


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
        dtv_data = await hass.async_add_executor_job(
            get_dtv_data, hass, entry.data[CONF_HOST]
        )
    except RequestException:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = dtv_data

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
