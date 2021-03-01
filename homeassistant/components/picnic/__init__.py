"""The Picnic integration."""
import asyncio

from python_picnic_api import PicnicAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_USERNAME, CONF_COUNTRY_CODE, CONF_PASSWORD

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Picnic component."""
    return True


def create_picnic_client(entry: ConfigEntry):
    return PicnicAPI(
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
        country_code=entry.data.get(CONF_COUNTRY_CODE),
        store=False
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Picnic from a config entry."""
    picnic_client = await hass.async_add_executor_job(
        create_picnic_client, entry
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = picnic_client

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
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
