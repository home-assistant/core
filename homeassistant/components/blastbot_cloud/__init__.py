"""The Blastbot Cloud integration."""
import asyncio

from blastbot_cloud_api.api import BlastbotCloudAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, LOGGER

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


# List the platforms that you want to support.
PLATFORMS = ["switch", "climate", "remote"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Blastbot Cloud component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Blastbot Cloud from a config entry."""
    # Assign configuration variables.
    # The configuration check takes care they are present.
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    # Setup connection with devices/cloud
    api = BlastbotCloudAPI()
    successful_login = await api.async_login(username, password)

    if not successful_login:
        LOGGER.error("Could not connect to Blastbot Cloud")
        await api.async_close()
        return

    async def async_on_hass_shutdown(event):
        """Handle shutdown tasks."""
        await api.async_close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_on_hass_shutdown)

    # Store an API object for your platforms to access
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = dict()
    hass.data[DOMAIN][entry.entry_id] = api

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
        if DOMAIN in hass.data:
            api = hass.data[DOMAIN][entry.entry_id]
            await api.async_close()
            hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
