"""The Picnic integration."""
import asyncio

from python_picnic_api import PicnicAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from .const import CONF_API, CONF_COORDINATOR, CONF_COUNTRY_CODE, DOMAIN
from .coordinator import PicnicUpdateCoordinator

PLATFORMS = ["sensor"]


def create_picnic_client(entry: ConfigEntry):
    """Create an instance of the PicnicAPI client."""
    return PicnicAPI(
        auth_token=entry.data.get(CONF_ACCESS_TOKEN),
        country_code=entry.data.get(CONF_COUNTRY_CODE),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Picnic from a config entry."""
    picnic_client = await hass.async_add_executor_job(create_picnic_client, entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_API: picnic_client,
        CONF_COORDINATOR: PicnicUpdateCoordinator(hass, picnic_client, entry),
    }

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
