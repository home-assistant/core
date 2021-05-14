"""The HVV integration."""

from homeassistant.components.binary_sensor import DOMAIN as DOMAIN_BINARY_SENSOR
from homeassistant.components.sensor import DOMAIN as DOMAIN_SENSOR
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .hub import GTIHub

PLATFORMS = [DOMAIN_SENSOR, DOMAIN_BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up HVV from a config entry."""

    hub = GTIHub(
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        aiohttp_client.async_get_clientsession(hass),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = hub

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
